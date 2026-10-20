/**
 * @file can_port.c
 * @brief Réalisation bxCAN de l'interface CAN abstraite, pour le STM32L476 (pont CAN-USB).
 *
 * Copie du port F103 (même bxCAN), adaptée au L476. Mêmes principes que le port FDCAN du G431 :
 *
 * **L'ISR ne fait que recopier.** La routine de réception date la trame et la
 * dépose dans le tampon circulaire ; tout le reste est dans la boucle principale.
 *
 * **Aucun compteur d'erreur n'est réimplémenté.** État et compteurs sont lus
 * dans le registre `ESR` (TEC, REC, LEC, BOFF, EPVF, EWGF) ; les débordements de
 * FIFO viennent du drapeau matériel `FOVR0`.
 *
 * Différences avec le FDCAN, toutes documentées dans RM0351 (§ bxCAN) :
 * - le bouclage de la phase 1 est le **bouclage combiné au mode silencieux** :
 *   en bouclage simple, bxCAN émet quand même sur CANTX ; combiné au mode
 *   silencieux, « the CANTX pin is held recessive » ;
 * - la reprise après bus-off est **matérielle** (bit ABOM), sans logiciel ;
 * - sans filtre configuré, bxCAN ne reçoit **rien** : un banc de filtres en mode
 *   masque, masque nul, accepte toutes les trames ;
 * - bxCAN ne connaît pas le CAN FD : une telle trame est une erreur de forme.
 */

#include "can_port.h"

#include "board.h"
#include "clock.h"
#include "icd_gen.h" /* BENCH_CLASSIC_MAX_DLC / _MAX_ID */

/* Codage des segments dans CAN_BTR : la HAL attend (n - 1) décalé à la position
 * du champ. Le port calcule ce codage à partir des valeurs de board.h ; si la
 * HAL changeait de convention, la compilation doit échouer — même leçon que le
 * DLC de la HAL G4. */
_Static_assert(CAN_BS1_6TQ == (5u << CAN_BTR_TS1_Pos), "Codage de TS1 inattendu dans la HAL L4");
_Static_assert(CAN_BS2_1TQ == (0u << CAN_BTR_TS2_Pos), "Codage de TS2 inattendu dans la HAL L4");
_Static_assert(CAN_BS2_2TQ == (1u << CAN_BTR_TS2_Pos), "Codage de TS2 inattendu dans la HAL L4");
_Static_assert(CAN_SJW_2TQ == (1u << CAN_BTR_SJW_Pos), "Codage de SJW inattendu dans la HAL L4");

/** Contexte unique du port ; le L476 n'a qu'un seul bxCAN. */
static bench_port_can_t *s_port;

/* ------------------------------------------------------------------ temps -- */

/**
 * @brief Horodatage en microsecondes, dérivé du compteur de cycles DWT.
 *
 * Le Cortex-M4 du L476 dispose du compteur DWT, comme le G431.
 */
static void dwt_init(void) {
    /* Une seule fois : open() est rappelée par les modes de faute. */
    if ((DWT->CTRL & DWT_CTRL_CYCCNTENA_Msk) != 0u) {
        return;
    }
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

    gpio.Pin = BENCH_CAN_RX_PIN | BENCH_CAN_TX_PIN;
#ifdef BENCH_CAN_DIRECT
    /* Bus direct, sans transceiver : sorties à drain ouvert, tirées vers 3,3 V
     * par les résistances internes. Toutes les cartes reliées sur un même fil
     * forment un ET câblé : un 0 (dominant) tire le fil à la masse et l'emporte
     * sur un 1 (récessif). Même câblage que les nœuds G431 en bus direct ;
     * réservé aux essais sur table, sur quelques centimètres. */
    gpio.Mode = GPIO_MODE_AF_OD;
    gpio.Pull = GPIO_PULLUP;
#else
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_PULLUP;  /* RX récessive tant que le transceiver ne pilote pas */
#endif
    gpio.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
    gpio.Alternate = BENCH_CAN_AF;
    HAL_GPIO_Init(BENCH_CAN_RX_PORT, &gpio);
}

/* ------------------------------------------------------------------ ouverture */

/** Vrai si les segments tiennent dans les champs de CAN_BTR. */
static bool timing_valid(const bench_can_timing_t *t) {
    return t->prescaler >= 1u && t->prescaler <= 1024u && t->tseg1 >= 1u && t->tseg1 <= 16u &&
           t->tseg2 >= 1u && t->tseg2 <= 8u && t->sjw >= 1u && t->sjw <= 4u;
}

static bool port_open(void *ctx, const bench_can_config_t *config) {
    bench_port_can_t *port = (bench_port_can_t *)ctx;
    CAN_FilterTypeDef filter = {0};

    if (!timing_valid(&config->timing)) {
        return false;
    }

    dwt_init();
    gpio_init();
    __HAL_RCC_CAN1_CLK_ENABLE();

    /* open() peut être rappelée contrôleur démarré (modes de faute). */
    if (port->started) {
        (void)HAL_CAN_Stop(&port->hcan);
        port->started = false;
    }
    port->config = *config;

    port->hcan.Instance = CAN1;
    port->hcan.Init.Prescaler = config->timing.prescaler;
    if (config->loopback) {
        /* Bouclage + silencieux : CANTX maintenue récessive, rien sur le bus. */
        port->hcan.Init.Mode = CAN_MODE_SILENT_LOOPBACK;
    } else if (config->silent) {
        port->hcan.Init.Mode = CAN_MODE_SILENT;
    } else {
        port->hcan.Init.Mode = CAN_MODE_NORMAL;
    }
    port->hcan.Init.SyncJumpWidth = (uint32_t)(config->timing.sjw - 1u) << CAN_BTR_SJW_Pos;
    port->hcan.Init.TimeSeg1 = (uint32_t)(config->timing.tseg1 - 1u) << CAN_BTR_TS1_Pos;
    port->hcan.Init.TimeSeg2 = (uint32_t)(config->timing.tseg2 - 1u) << CAN_BTR_TS2_Pos;
    port->hcan.Init.TimeTriggeredMode = DISABLE;
    /* ABOM : reprise matérielle après 128 × 11 bits récessifs. Désactivée pour la
     * politique manuelle (mode de faute « bus-off maintenu »). */
    port->hcan.Init.AutoBusOff =
        (config->busoff_policy == BENCH_BUSOFF_AUTO) ? ENABLE : DISABLE;
    port->hcan.Init.AutoWakeUp = DISABLE;
    /* Indispensable à l'arbitrage : un nœud qui perd doit réessayer. */
    port->hcan.Init.AutoRetransmission = config->auto_retransmit ? ENABLE : DISABLE;
    port->hcan.Init.ReceiveFifoLocked = DISABLE;
    /* TXFP = 0 : les boîtes d'émission partent par ordre d'identifiant, comme la
     * file d'attente du FDCAN (TFQM = 1) sur le G431. */
    port->hcan.Init.TransmitFifoPriority = DISABLE;

    if (HAL_CAN_Init(&port->hcan) != HAL_OK) {
        return false;
    }

    /* Aucun filtre ne veut dire aucune réception sur bxCAN. Masque nul : tout
     * est accepté, y compris l'inattendu — c'est ce qui révèle un babbling idiot. */
    filter.FilterBank = 0u;
    filter.FilterMode = CAN_FILTERMODE_IDMASK;
    filter.FilterScale = CAN_FILTERSCALE_32BIT;
    filter.FilterIdHigh = 0u;
    filter.FilterIdLow = 0u;
    filter.FilterMaskIdHigh = 0u;
    filter.FilterMaskIdLow = 0u;
    filter.FilterFIFOAssignment = CAN_FILTER_FIFO0;
    filter.FilterActivation = ENABLE;
    filter.SlaveStartFilterBank = 14u;  /* sans effet sur un seul bxCAN */
    if (HAL_CAN_ConfigFilter(&port->hcan, &filter) != HAL_OK) {
        return false;
    }

    if (HAL_CAN_ActivateNotification(&port->hcan, CAN_IT_RX_FIFO0_MSG_PENDING |
                                                      CAN_IT_RX_FIFO0_OVERRUN |
                                                      CAN_IT_TX_MAILBOX_EMPTY) != HAL_OK) {
        return false;
    }
    port->armed_mailboxes = 0u;

    /* Les deux vecteurs ont la même priorité : aucun ne préempte l'autre, le
     * tampon garde un seul producteur à la fois et l'ordre du bus est conservé. */
    HAL_NVIC_SetPriority(CAN1_RX0_IRQn, 1u, 0u);
    HAL_NVIC_EnableIRQ(CAN1_RX0_IRQn);
    HAL_NVIC_SetPriority(CAN1_TX_IRQn, 1u, 0u);
    HAL_NVIC_EnableIRQ(CAN1_TX_IRQn);

    if (HAL_CAN_Start(&port->hcan) != HAL_OK) {
        return false;
    }
    port->started = true;
    return true;
}

/* ------------------------------------------------------------------ émission */

/** Émet une trame ; @p mailbox reçoit la boîte choisie par le contrôleur. */
static bool tx_common(bench_port_can_t *port, const bench_can_frame_t *frame,
                      uint32_t *mailbox) {
    CAN_TxHeaderTypeDef header = {0};

    /* Verrouillage CAN 2.0A classic, côté émission, comme sur le G431. */
    if (frame->dlc > BENCH_CLASSIC_MAX_DLC || frame->id > BENCH_CLASSIC_MAX_ID) {
        return false;
    }

    header.StdId = frame->id;
    header.ExtId = 0u;
    header.IDE = CAN_ID_STD;
    header.RTR = CAN_RTR_DATA;
    header.DLC = frame->dlc;
    header.TransmitGlobalTime = DISABLE;

    /* Échec si les trois boîtes d'émission sont pleines : l'appelant réessaie. */
    return HAL_CAN_AddTxMessage(&port->hcan, &header, frame->data, mailbox) == HAL_OK;
}

static bool port_send(void *ctx, const bench_can_frame_t *frame) {
    uint32_t mailbox;
    return tx_common((bench_port_can_t *)ctx, frame, &mailbox);
}

/**
 * Armement du protocole ARM/GO : la trame part dès que le bus est libre. La
 * boîte choisie est mémorisée ; sa fin d'émission, et elle seule, produira
 * l'élément BENCH_FRAME_OWN_TX.
 */
static bool port_arm(void *ctx, const bench_can_frame_t *frame) {
    bench_port_can_t *port = (bench_port_can_t *)ctx;
    uint32_t mailbox;

    if (!tx_common(port, frame, &mailbox)) {
        return false;
    }
    port->armed_id = frame->id;
    port->armed_mailboxes |= mailbox;
    return true;
}

/* --------------------------------------------------------------------- état */

static void port_status(void *ctx, bench_can_status_t *status) {
    bench_port_can_t *port = (bench_port_can_t *)ctx;
    const uint32_t esr = port->hcan.Instance->ESR;

    status->tec = (uint8_t)((esr & CAN_ESR_TEC_Msk) >> CAN_ESR_TEC_Pos);
    status->rec = (uint8_t)((esr & CAN_ESR_REC_Msk) >> CAN_ESR_REC_Pos);
    /* Même numérotation que le LEC du FDCAN : 1 bourrage, 2 forme, 3 acquittement,
     * 4 bit récessif, 5 bit dominant, 6 CRC. */
    status->last_error_code = (uint8_t)((esr & CAN_ESR_LEC_Msk) >> CAN_ESR_LEC_Pos);

    if ((esr & CAN_ESR_BOFF) != 0u) {
        status->state = BENCH_CAN_BUS_OFF;
    } else if ((esr & CAN_ESR_EPVF) != 0u) {
        status->state = BENCH_CAN_ERROR_PASSIVE;
    } else if ((esr & CAN_ESR_EWGF) != 0u) {
        status->state = BENCH_CAN_ERROR_WARNING;
    } else {
        status->state = BENCH_CAN_ERROR_ACTIVE;
    }

    status->rx_fifo_lost = port->rx_fifo_lost;
    status->non_classic_rx = port->non_classic_rx;
    status->ext_id_rx = port->ext_id_rx;
}

static bool port_recover(void *ctx) {
    bench_port_can_t *port = (bench_port_can_t *)ctx;

    if ((port->hcan.Instance->ESR & CAN_ESR_BOFF) == 0u) {
        return true;
    }
    /* Sans ABOM, la sortie du bus-off passe par l'entrée puis la sortie du mode
     * d'initialisation ; la séquence de 128 × 11 bits récessifs suit (RM0351). */
    (void)HAL_CAN_Stop(&port->hcan);
    return HAL_CAN_Start(&port->hcan) == HAL_OK;
}

static void port_set_silent(void *ctx, bool silent) {
    bench_port_can_t *port = (bench_port_can_t *)ctx;
    bench_can_config_t config = port->config;

    /* Mode silencieux du contrôleur : il reçoit mais n'émet que des bits
     * récessifs, donc n'acquitte pas. Même sémantique que le mode moniteur du
     * FDCAN ; couvre aussi le mode « arrêt d'acquittement » de N4. */
    config.silent = silent;
    (void)port_open(port, &config);
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

void bench_port_can_bind(bench_port_can_t *port, bench_ring_t *rx_ring, bench_can_t *out) {
    port->rx_ring = rx_ring;
    port->rx_fifo_lost = 0u;
    port->non_classic_rx = 0u;
    port->ext_id_rx = 0u;
    port->started = false;
    s_port = port;

    out->ops = &s_ops;
    out->ctx = port;
}

void bench_port_can_close(bench_port_can_t *port) {
    if (port->started) {
        (void)HAL_CAN_Stop(&port->hcan);
        port->started = false;
    }
}

void bench_port_can_poll(bench_port_can_t *port) {
    (void)port;  /* reprise après bus-off matérielle (ABOM), voir can_port.h */
}

/* ------------------------------------------------------------ interruptions */

void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *hcan) {
    CAN_RxHeaderTypeDef header;
    bench_can_frame_t frame;

    if (s_port == NULL) {
        return;
    }

    /* Tout ce que fait l'ISR : dater, recopier, compter, sortir. bxCAN ne
     * stocke que 8 octets de données, le tampon ne peut pas déborder. */
    while (HAL_CAN_GetRxFifoFillLevel(hcan, CAN_RX_FIFO0) > 0u) {
        if (HAL_CAN_GetRxMessage(hcan, CAN_RX_FIFO0, &header, frame.data) != HAL_OK) {
            break;
        }
        if (header.IDE != CAN_ID_STD) {
            if (s_port->ext_id_rx != UINT8_MAX) {
                s_port->ext_id_rx++;
            }
            continue;  /* identifiant hors ICD : compté, mais non transmis */
        }

        frame.timestamp_us = now_us(NULL);
        frame.flags = 0u;
        frame.id = (uint16_t)header.StdId;
        /* En CAN 2.0, un DLC de 9 à 15 signifie 8 octets. */
        frame.dlc = (header.DLC > BENCH_CLASSIC_MAX_DLC) ? (uint8_t)BENCH_CLASSIC_MAX_DLC
                                                        : (uint8_t)header.DLC;
        for (uint8_t i = frame.dlc; i < BENCH_CLASSIC_MAX_DLC; i++) {
            frame.data[i] = 0u;  /* pas de reste de pile au-delà du DLC */
        }
        (void)bench_ring_push(s_port->rx_ring, &frame);
    }
}

void HAL_CAN_ErrorCallback(CAN_HandleTypeDef *hcan) {
    if (s_port == NULL) {
        return;
    }
    /* Débordement matériel de la FIFO 0 : distingué, dans le heartbeat, du
     * débordement de notre tampon logiciel. */
    if ((hcan->ErrorCode & HAL_CAN_ERROR_RX_FOV0) != 0u) {
        if (s_port->rx_fifo_lost != UINT16_MAX) {
            s_port->rx_fifo_lost++;
        }
    }
    (void)HAL_CAN_ResetError(hcan);
}

/** Fin d'émission réussie d'une boîte : confirme la trame contendante armée. */
static void on_tx_complete(uint32_t mailbox) {
    if (s_port == NULL || (s_port->armed_mailboxes & mailbox) == 0u) {
        return;  /* heartbeat ou trame de faute : sans effet sur l'arbitrage */
    }
    s_port->armed_mailboxes &= ~mailbox;

    bench_can_frame_t event = {0};
    event.timestamp_us = now_us(NULL);
    event.id = s_port->armed_id;
    event.dlc = 8u;
    event.flags = BENCH_FRAME_OWN_TX;
    (void)bench_ring_push(s_port->rx_ring, &event);
}

void HAL_CAN_TxMailbox0CompleteCallback(CAN_HandleTypeDef *hcan) {
    (void)hcan;
    on_tx_complete(CAN_TX_MAILBOX0);
}

void HAL_CAN_TxMailbox1CompleteCallback(CAN_HandleTypeDef *hcan) {
    (void)hcan;
    on_tx_complete(CAN_TX_MAILBOX1);
}

void HAL_CAN_TxMailbox2CompleteCallback(CAN_HandleTypeDef *hcan) {
    (void)hcan;
    on_tx_complete(CAN_TX_MAILBOX2);
}

void CAN1_TX_IRQHandler(void) {
    if (s_port != NULL) {
        HAL_CAN_IRQHandler(&s_port->hcan);
    }
}

void CAN1_RX0_IRQHandler(void) {
    if (s_port != NULL) {
        HAL_CAN_IRQHandler(&s_port->hcan);
    }
}
