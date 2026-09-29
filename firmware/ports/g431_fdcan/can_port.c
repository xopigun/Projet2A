/**
 * @file can_port.c
 * @brief Réalisation FDCAN de l'interface CAN abstraite, pour le STM32G431.
 *
 * Deux principes structurent ce fichier.
 *
 * **L'ISR ne fait que recopier.** La routine de réception lit la trame, la date
 * et la dépose dans le tampon circulaire. Décodage, affichage et capteurs sont
 * dans la boucle principale. Sans cela, le banc mesurerait ses propres retards
 * logiciels au lieu du comportement du bus.
 *
 * **Aucun compteur d'erreur n'est réimplémenté.** L'état et les compteurs sont
 * lus dans les registres du périphérique : `PSR` pour LEC, EP, EW et BO, `ECR`
 * pour TEC et REC, `RF0L`/interruption `RF0L` pour les pertes FIFO. Un compteur
 * logiciel refléterait notre interprétation, pas le matériel.
 *
 * Le mode FDCAN est **Classic** : CAN 2.0A, identifiants 11 bits, 500 kbit/s,
 * sans commutation de débit ni format FD.
 */

#include "can_port.h"

#include "board.h"
#include "clock.h"
#include "icd_gen.h"  /* BENCH_CLASSIC_MAX_DLC / _MAX_ID */

/* Le codage du DLC dans l'API HAL a change entre versions : les anciennes HAL
 * attendaient n << 16, les versions epinglees ici attendent n. Si le sous-module
 * etait un jour retrograde, la compilation doit echouer plutot que d'emettre
 * silencieusement des trames de DLC nul. */
_Static_assert(FDCAN_DLC_BYTES_8 == 8u,
               "Codage du DLC FDCAN inattendu : verifier la version de la HAL G4");
_Static_assert(FDCAN_DLC_BYTES_0 == 0u,
               "Codage du DLC FDCAN inattendu : verifier la version de la HAL G4");

/** Contexte unique du port ; le G431KB n'a qu'un seul FDCAN. */
static bench_g431_can_t *s_port;

/* ------------------------------------------------------------------ temps -- */

/**
 * @brief Horodatage en microsecondes, dérivé du compteur de cycles DWT.
 *
 * Le compteur de millisecondes de la HAL est trop grossier : à 500 kbit/s une
 * trame de 8 octets dure environ 220 µs, donc l'ordre des trames d'un cycle
 * d'arbitrage ne serait pas discernable.
 */
static void dwt_init(void) {
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0u;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t now_us(void *ctx) {
    (void)ctx;
    return DWT->CYCCNT / (BENCH_SYSCLK_HZ / 1000000u);
}

/* ---------------------------------------------------------------- broches -- */

static void gpio_init(void) {
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin = BENCH_CAN_RX_PIN | BENCH_CAN_TX_PIN;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
    gpio.Alternate = BENCH_CAN_AF;
    HAL_GPIO_Init(BENCH_CAN_RX_PORT, &gpio);

#if BENCH_HAS_TRANSCEIVER_STANDBY
    /* Broche S du TJA1051T/3 : bas = mode normal. Le mode silencieux passe par
     * le mode moniteur du contrôleur, pas par cette broche (voir set_silent). */
    gpio.Pin = BENCH_TRX_S_PIN;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Alternate = 0u;
    HAL_GPIO_Init(BENCH_TRX_S_PORT, &gpio);
    HAL_GPIO_WritePin(BENCH_TRX_S_PORT, BENCH_TRX_S_PIN, GPIO_PIN_RESET);
#endif

    /* SB2 et SB3 étant fermés, PA5 et PA6 rejoignent PB7 et PA15 par A4 et A5 :
     * les laisser en entrée sans tirage évite un conflit sur le bus I2C
     * (UM2397 Table 9). */
    gpio.Pin = BENCH_FLOATING_PINS;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(BENCH_FLOATING_PORT, &gpio);
}

/* ------------------------------------------------------------------ ouverture */

static bool port_open(void *ctx, const bench_can_config_t *config) {
    bench_g431_can_t *port = (bench_g431_can_t *)ctx;

    dwt_init();
    gpio_init();
    __HAL_RCC_FDCAN_CLK_ENABLE();

    port->hfdcan.Instance = FDCAN1;
    port->hfdcan.Init.ClockDivider = FDCAN_CLOCK_DIV1;
    port->hfdcan.Init.FrameFormat = FDCAN_FRAME_CLASSIC;
    if (config->loopback) {
        /* Bouclage interne : rien n'est emis sur PA12, aucun transceiver requis. */
        port->hfdcan.Init.Mode = FDCAN_MODE_INTERNAL_LOOPBACK;
    } else if (config->silent) {
        port->hfdcan.Init.Mode = FDCAN_MODE_BUS_MONITORING;
    } else {
        port->hfdcan.Init.Mode = FDCAN_MODE_NORMAL;
    }

    /* La retransmission automatique est indispensable : sans elle, un nœud qui
     * perd l'arbitrage abandonne sa trame et le test d'arbitrage perd son sens.
     * Le champ HAL est inversé (« AutoRetransmission »), d'où la négation. */
    port->hfdcan.Init.AutoRetransmission =
        config->auto_retransmit ? ENABLE : DISABLE;
    port->hfdcan.Init.TransmitPause = DISABLE;
    port->hfdcan.Init.ProtocolException = DISABLE;

    port->hfdcan.Init.NominalPrescaler = config->timing.prescaler;
    port->hfdcan.Init.NominalSyncJumpWidth = config->timing.sjw;
    port->hfdcan.Init.NominalTimeSeg1 = config->timing.tseg1;
    port->hfdcan.Init.NominalTimeSeg2 = config->timing.tseg2;

    /* Inutilisés en Classic, mais la HAL valide les champs. */
    port->hfdcan.Init.DataPrescaler = 1u;
    port->hfdcan.Init.DataSyncJumpWidth = 1u;
    port->hfdcan.Init.DataTimeSeg1 = 1u;
    port->hfdcan.Init.DataTimeSeg2 = 1u;

    port->hfdcan.Init.StdFiltersNbr = 0u;
    port->hfdcan.Init.ExtFiltersNbr = 0u;
    /* Mode file d'attente (TFQM = 1) : l'erratum ES0431 §2.15.2, inversion de
     * deux messages de la FIFO, ne concerne que le mode FIFO (TFQM = 0).
     * L'erratum §2.15.1 exige le filtrage de front (CCCR.EFBI), que la HAL ne
     * positionne jamais et qui vaut 0 au reset (RM0440 §44.4.6). */
    port->hfdcan.Init.TxFifoQueueMode = FDCAN_TX_QUEUE_OPERATION;

    /* Le peripherique s'appelle FDCAN mais le protocole retenu est CAN 2.0A
     * classic : on refuse d'ouvrir si la configuration a derive. */
    if (port->hfdcan.Init.FrameFormat != FDCAN_FRAME_CLASSIC) {
        return false;
    }

    if (HAL_FDCAN_Init(&port->hfdcan) != HAL_OK) {
        return false;
    }

    /* Aucun filtre : le banc doit voir tout le trafic, y compris les trames
     * qu'il n'attend pas — c'est ce qui permet de détecter un babbling idiot. */
    if (HAL_FDCAN_ConfigGlobalFilter(&port->hfdcan, FDCAN_ACCEPT_IN_RX_FIFO0,
                                     FDCAN_ACCEPT_IN_RX_FIFO0, FDCAN_FILTER_REMOTE,
                                     FDCAN_FILTER_REMOTE) != HAL_OK) {
        return false;
    }

    port->busoff_policy = config->busoff_policy;
    port->silent = config->silent;

    /* Sur FDCAN la reprise après bus-off est logicielle : le matériel n'a pas
     * d'équivalent du bit ABOM de bxCAN. Le bit INIT est remis à zéro par
     * bench_g431_can_poll() lorsque la politique est automatique. */
    if (HAL_FDCAN_ActivateNotification(&port->hfdcan,
                                       FDCAN_IT_RX_FIFO0_NEW_MESSAGE |
                                           FDCAN_IT_RX_FIFO0_MESSAGE_LOST |
                                           FDCAN_IT_BUS_OFF | FDCAN_IT_ERROR_PASSIVE |
                                           FDCAN_IT_ERROR_WARNING,
                                       0u) != HAL_OK) {
        return false;
    }

    HAL_NVIC_SetPriority(FDCAN1_IT0_IRQn, 1u, 0u);
    HAL_NVIC_EnableIRQ(FDCAN1_IT0_IRQn);

    return HAL_FDCAN_Start(&port->hfdcan) == HAL_OK;
}

/* ------------------------------------------------------------------ émission */

static bool tx_common(bench_g431_can_t *port, const bench_can_frame_t *frame) {
    FDCAN_TxHeaderTypeDef header = {0};

    /* Verrouillage CAN 2.0A classic, cote emission. Une trame hors specification
     * est refusee ici plutot que d'etre emise et de perturber le bus : le banc
     * doit mesurer le comportement des autres, pas introduire ses propres
     * anomalies. Les constantes de l'ICD sont deja verifiees a la compilation
     * par les _Static_assert de icd_gen.h ; ce controle couvre les trames
     * construites dynamiquement, notamment par BENCH_CFG. */
    if (frame->dlc > BENCH_CLASSIC_MAX_DLC || frame->id > BENCH_CLASSIC_MAX_ID) {
        return false;
    }

    header.Identifier = frame->id;
    header.IdType = FDCAN_STANDARD_ID;
    header.TxFrameType = FDCAN_DATA_FRAME;
    /* Depuis la HAL G4 v1.2.x, FDCAN_DLC_BYTES_n vaut n pour n <= 8 : le DLC se
     * passe tel quel. Les anciennes versions attendaient n << 16 ; un tel decalage
     * ici ferait indexer par la HAL un tableau de 16 cases avec 0x80000. Voir
     * l'assertion statique en tete de fichier. */
    header.DataLength = (uint32_t)frame->dlc;
    header.ErrorStateIndicator = FDCAN_ESI_ACTIVE;
    header.BitRateSwitch = FDCAN_BRS_OFF;
    header.FDFormat = FDCAN_CLASSIC_CAN;
    header.TxEventFifoControl = FDCAN_NO_TX_EVENTS;  /* FIFO d'evenements jamais lue */
    header.MessageMarker = 0u;

    return HAL_FDCAN_AddMessageToTxFifoQ(&port->hfdcan, &header, frame->data) == HAL_OK;
}

static bool port_send(void *ctx, const bench_can_frame_t *frame) {
    return tx_common((bench_g431_can_t *)ctx, frame);
}

/**
 * @brief Place la trame de test dans la file d'émission, sans attendre.
 *
 * C'est l'armement du protocole ARM/GO. La trame partira dès que le bus sera
 * libre ; comme GO l'occupe encore, tous les contendants démarrent au même bit.
 */
static bool port_arm(void *ctx, const bench_can_frame_t *frame) {
    return tx_common((bench_g431_can_t *)ctx, frame);
}

/* --------------------------------------------------------------------- état */

static void port_status(void *ctx, bench_can_status_t *status) {
    bench_g431_can_t *port = (bench_g431_can_t *)ctx;

    /* Lecture directe des registres : PSR pour l'état du protocole, ECR pour
     * les compteurs. PSR est à effacement à la lecture pour certains bits, on ne
     * le lit donc qu'ici, à un seul endroit. */
    const uint32_t psr = port->hfdcan.Instance->PSR;
    const uint32_t ecr = port->hfdcan.Instance->ECR;

    status->tec = (uint8_t)(ecr & FDCAN_ECR_TEC_Msk);
    status->rec = (uint8_t)((ecr & FDCAN_ECR_REC_Msk) >> FDCAN_ECR_REC_Pos);
    status->last_error_code = (uint8_t)(psr & FDCAN_PSR_LEC_Msk);

    if ((psr & FDCAN_PSR_BO) != 0u) {
        status->state = BENCH_CAN_BUS_OFF;
    } else if ((psr & FDCAN_PSR_EP) != 0u) {
        status->state = BENCH_CAN_ERROR_PASSIVE;
    } else if ((psr & FDCAN_PSR_EW) != 0u) {
        status->state = BENCH_CAN_ERROR_WARNING;
    } else {
        status->state = BENCH_CAN_ERROR_ACTIVE;
    }

    status->rx_fifo_lost = port->rx_fifo_lost;
    status->non_classic_rx = port->non_classic_rx;
    status->ext_id_rx = port->ext_id_rx;
}

static bool port_recover(void *ctx) {
    bench_g431_can_t *port = (bench_g431_can_t *)ctx;

    if ((port->hfdcan.Instance->PSR & FDCAN_PSR_BO) == 0u) {
        return true;
    }
    /* Sortie de bus-off : remettre INIT à zéro lance la séquence de reprise
     * (128 occurrences de 11 bits récessifs). */
    CLEAR_BIT(port->hfdcan.Instance->CCCR, FDCAN_CCCR_INIT);
    return true;
}

static void port_set_silent(void *ctx, bool silent) {
    bench_g431_can_t *port = (bench_g431_can_t *)ctx;

    /* Le mode silencieux passe par le mode moniteur du contrôleur plutôt que par
     * la broche S du transceiver : sémantique identique sur G431 et F103, pas de
     * dégradation du récepteur, et indépendance vis-à-vis du modèle de
     * transceiver. Il couvre aussi le mode « arrêt d'acquittement » de N4, qui
     * n'existe pas séparément sur ces contrôleurs. */
    port->silent = silent;
    port->hfdcan.Init.Mode = silent ? FDCAN_MODE_BUS_MONITORING : FDCAN_MODE_NORMAL;

    HAL_FDCAN_Stop(&port->hfdcan);
    (void)HAL_FDCAN_Init(&port->hfdcan);
    (void)HAL_FDCAN_Start(&port->hfdcan);
}

static const bench_can_ops_t s_ops = {
    .open = port_open,
    .send = port_send,
    .arm = port_arm,
    .status = port_status,
    .recover = port_recover,
    .set_silent = port_set_silent,
    .now_us = now_us,
};

void bench_g431_can_bind(bench_g431_can_t *port, bench_ring_t *rx_ring, bench_can_t *out) {
    port->rx_ring = rx_ring;
    port->rx_fifo_lost = 0u;
    port->non_classic_rx = 0u;
    port->ext_id_rx = 0u;
    s_port = port;

    out->ops = &s_ops;
    out->ctx = port;
}

void bench_g431_can_poll(bench_g431_can_t *port) {
    if (port->busoff_policy != BENCH_BUSOFF_AUTO) {
        return;
    }
    if ((port->hfdcan.Instance->PSR & FDCAN_PSR_BO) != 0u) {
        CLEAR_BIT(port->hfdcan.Instance->CCCR, FDCAN_CCCR_INIT);
    }
}

/* ------------------------------------------------------------ interruptions */

void HAL_FDCAN_RxFifo0Callback(FDCAN_HandleTypeDef *hfdcan, uint32_t interrupts) {
    FDCAN_RxHeaderTypeDef header;
    bench_can_frame_t frame;

    if (s_port == NULL) {
        return;
    }

    if ((interrupts & FDCAN_IT_RX_FIFO0_MESSAGE_LOST) != 0u) {
        /* Perte matérielle : la FIFO a débordé avant que nous l'ayons vidée.
         * Distinguée du débordement de notre tampon logiciel dans le heartbeat. */
        if (s_port->rx_fifo_lost != UINT16_MAX) {
            s_port->rx_fifo_lost++;
        }
    }

    if ((interrupts & FDCAN_IT_RX_FIFO0_NEW_MESSAGE) == 0u) {
        return;
    }

    /* Tout ce que fait l'ISR : dater, recopier, compter, sortir. */
    while (HAL_FDCAN_GetRxMessage(hfdcan, FDCAN_RX_FIFO0, &header, frame.data) == HAL_OK) {
        /* Le bus est en CAN 2.0A classic : ces deux compteurs doivent rester
         * nuls. Ils sont remontes dans le heartbeat pour qu'une trame etrangere
         * au standard commun se voie, au lieu d'etre silencieusement ignoree.
         *
         * Une trame CAN FD sur un bus classic est le plus souvent rejetee au
         * niveau protocole et apparait comme une erreur de forme dans LEC, sans
         * jamais remonter jusqu'ici ; ce compteur ne capte donc que celles que
         * le controleur accepte de presenter. Les identifiants 29 bits, eux,
         * sont des trames CAN 2.0B parfaitement valides et sont bien comptes. */
        if (header.FDFormat != FDCAN_CLASSIC_CAN && s_port->non_classic_rx != UINT8_MAX) {
            s_port->non_classic_rx++;
        }
        if (header.IdType != FDCAN_STANDARD_ID) {
            if (s_port->ext_id_rx != UINT8_MAX) {
                s_port->ext_id_rx++;
            }
            continue;  /* identifiant hors ICD : compte, mais non transmis */
        }

        frame.timestamp_us = now_us(NULL);
        frame.id = (uint16_t)header.Identifier;
        frame.dlc = (uint8_t)header.DataLength;  /* FDCAN_DLC_BYTES_n == n */
        (void)bench_ring_push(s_port->rx_ring, &frame);
    }
}

void FDCAN1_IT0_IRQHandler(void) {
    if (s_port != NULL) {
        HAL_FDCAN_IRQHandler(&s_port->hfdcan);
    }
}
