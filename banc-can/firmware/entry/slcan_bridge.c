/**
 * @file slcan_bridge.c
 * @brief Pont CAN-USB : une Nucleo-L476RG se comporte comme un CANable en slcan.
 *
 * Remplace `main.c` pour la cible `bridge` (presets `bridge` et `bridge-direct`).
 * Le PC (python-can, `canbench --interface slcan --channel COMx`) ouvre le port
 * COM virtuel du ST-LINK et parle le protocole slcan ; le pont transmet au bus
 * les trames demandées et renvoie au PC toutes celles qu'il y voit.
 *
 * **Le port série est le flux slcan, rien d'autre.** Aucun printf, aucun
 * message de diagnostic : un octet de trop serait lu comme un début de trame.
 * L'état se lit par la commande `F`, et LD2 clignote à chaque trame transmise
 * au PC.
 *
 * **Participation au bus.** `O` ouvre en mode normal : le pont acquitte les
 * trames qu'il reçoit, comme n'importe quel nœud, et peut en émettre. `L` ouvre
 * en écoute seule (mode silencieux du bxCAN) : il n'acquitte rien et ne perturbe
 * pas le bus, mais il faut alors qu'un autre nœud acquitte, sans quoi l'émetteur
 * voit une erreur d'acquittement.
 *
 * **Tampons.** L'ISR dépose les trames dans un tampon (voir can_port.c) ; la
 * boucle les met en forme dans un tampon d'octets que l'USART vide. Si le PC ne
 * suit pas (115200 bauds : environ 500 trames par seconde au plus), les trames
 * sont perdues entières, jamais tronquées, et la commande `F` le signale.
 */

#include "app/slcan.h"
#include "board.h"
#include "can_port.h"
#include "clock.h"
#include "serial.h"
#include "util/ring_buffer.h"

#ifndef BENCH_BRIDGE_TX_CAPACITY
#define BENCH_BRIDGE_TX_CAPACITY 4096u  /* puissance de deux */
#endif

#define BRIDGE_VERSION_REPLY "V0101\r"  /* matériel 01, logiciel 01 */
#define BRIDGE_SERIAL_REPLY  "N0476\r"

static bench_ring_t        s_rx_ring;
static bench_port_can_t    s_port;
static bench_can_t         s_can;
static bench_slcan_parser_t s_parser;

static uint8_t           s_tx[BENCH_BRIDGE_TX_CAPACITY];
static uint32_t          s_tx_head;  /* prochaine case à écrire */
static uint32_t          s_tx_tail;  /* prochaine case à émettre */

static bool     s_open;
static bool     s_listen;
static uint32_t s_bitrate = 500000u;  /* S6 par défaut, comme un CANable */
static bool     s_lost;               /* trame perdue depuis la dernière commande F */
static uint32_t s_led_off_ms;

/* ------------------------------------------------------------ flux vers le PC */

static uint32_t tx_free(void) {
    return BENCH_BRIDGE_TX_CAPACITY - (s_tx_head - s_tx_tail);
}

/** Met @p length octets en file d'émission, ou aucun s'ils ne tiennent pas. */
static bool emit(const char *data, size_t length) {
    if (length > tx_free()) {
        return false;
    }
    for (size_t i = 0u; i < length; i++) {
        s_tx[s_tx_head++ & (BENCH_BRIDGE_TX_CAPACITY - 1u)] = (uint8_t)data[i];
    }
    return true;
}

static void reply(char code) {
    (void)emit(&code, 1u);
}

/** Vide autant d'octets que l'USART en accepte ; ne bloque jamais. */
static void pump_tx(void) {
    while (s_tx_tail != s_tx_head && bench_vcp_can_write()) {
        bench_vcp_write(s_tx[s_tx_tail++ & (BENCH_BRIDGE_TX_CAPACITY - 1u)]);
    }
}

/* --------------------------------------------------------------- contrôleur */

static bool can_open(bool listen) {
    bench_can_config_t config = {0};

    config.timing.prescaler =
        (uint16_t)(BENCH_PCLK1_HZ / (s_bitrate * BENCH_CAN_TQ_PER_BIT));
    config.timing.tseg1 = BENCH_CAN_TSEG1;
    config.timing.tseg2 = BENCH_CAN_TSEG2;
    config.timing.sjw = BENCH_CAN_SJW;
    config.busoff_policy = BENCH_BUSOFF_AUTO;
    config.silent = listen;
    config.loopback = false;
    config.auto_retransmit = true;  /* un nœud qui perd l'arbitrage doit réessayer */

    return s_can.ops->open(s_can.ctx, &config);
}

static void can_close(void) {
    bench_port_can_close(&s_port);
    s_open = false;
    /* Les trames restantes appartiennent à la session précédente. */
    bench_can_frame_t discard;
    while (bench_ring_pop(&s_rx_ring, &discard)) {
    }
}

/* ---------------------------------------------------------------- commandes */

static void handle_open(bool listen) {
    if (s_open && s_listen == listen) {
        reply(BENCH_SLCAN_OK);  /* python-can envoie « O » deux fois : sans effet */
        return;
    }
    can_close();
    if (can_open(listen)) {
        s_open = true;
        s_listen = listen;
        reply(BENCH_SLCAN_OK);
    } else {
        reply(BENCH_SLCAN_ERR);
    }
}

static void handle_status(void) {
    bench_can_status_t status = {0};
    char out[5];
    static const char hex[] = "0123456789ABCDEF";

    if (s_open) {
        s_can.ops->status(s_can.ctx, &status);
    }
    const uint8_t flags = bench_slcan_status_flags(&status, s_lost);
    s_lost = false;

    out[0] = 'F';
    out[1] = hex[flags >> 4];
    out[2] = hex[flags & 0xFu];
    out[3] = BENCH_SLCAN_OK;
    (void)emit(out, 4u);
}

static void execute(const bench_slcan_cmd_t *cmd) {
    switch (cmd->type) {
    case BENCH_SLCAN_NONE:
        break;
    case BENCH_SLCAN_INVALID:
        reply(BENCH_SLCAN_ERR);
        break;
    case BENCH_SLCAN_OPEN:
        handle_open(false);
        break;
    case BENCH_SLCAN_LISTEN:
        handle_open(true);
        break;
    case BENCH_SLCAN_CLOSE:
        can_close();
        reply(BENCH_SLCAN_OK);
        break;
    case BENCH_SLCAN_BITRATE:
        if (s_open) {
            reply(BENCH_SLCAN_ERR);  /* le débit ne change que bus fermé */
        } else {
            s_bitrate = cmd->bitrate_bps;
            reply(BENCH_SLCAN_OK);
        }
        break;
    case BENCH_SLCAN_SEND:
        if (s_open && !s_listen && s_can.ops->send(s_can.ctx, &cmd->frame)) {
            (void)emit("z\r", 2u);
        } else {
            reply(BENCH_SLCAN_ERR);  /* fermé, écoute seule ou boîtes pleines */
        }
        break;
    case BENCH_SLCAN_VERSION:
        (void)emit(BRIDGE_VERSION_REPLY, sizeof(BRIDGE_VERSION_REPLY) - 1u);
        break;
    case BENCH_SLCAN_SERIAL:
        (void)emit(BRIDGE_SERIAL_REPLY, sizeof(BRIDGE_SERIAL_REPLY) - 1u);
        break;
    case BENCH_SLCAN_FLAGS:
        handle_status();
        break;
    case BENCH_SLCAN_ACCEPT:
        reply(BENCH_SLCAN_OK);
        break;
    }
}

/* ------------------------------------------------------------------- boucle */

static void led_init(void) {
    GPIO_InitTypeDef gpio = {0};

    BENCH_LED_CLK_ENABLE();
    gpio.Pin = BENCH_LED_PIN;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(BENCH_LED_PORT, &gpio);
    HAL_GPIO_WritePin(BENCH_LED_PORT, BENCH_LED_PIN, GPIO_PIN_RESET);
}

/** Met en forme les trames reçues du bus et les place dans le flux vers le PC. */
static void forward_frames(uint32_t now_ms) {
    bench_can_frame_t frame;
    char line[BENCH_SLCAN_FRAME_MAX];

    /* Une borne par passage : l'écoute des commandes du PC ne doit pas attendre. */
    for (uint32_t n = 0u; n < 8u && bench_ring_pop(&s_rx_ring, &frame); n++) {
        if (!s_open || (frame.flags & BENCH_FRAME_OWN_TX) != 0u) {
            continue;
        }
        const size_t length = bench_slcan_format_frame(&frame, line, sizeof line);
        if (length == 0u || !emit(line, length)) {
            s_lost = true;  /* tampon plein : la trame est perdue entière */
            continue;
        }
        HAL_GPIO_WritePin(BENCH_LED_PORT, BENCH_LED_PIN, GPIO_PIN_SET);
        s_led_off_ms = now_ms + BENCH_LED_PULSE_MS;
    }
}

int main(void) {
    HAL_Init();
    bench_clock_config();
    led_init();

    if (!bench_vcp_open()) {
        bench_fatal("USART2");
    }

    bench_ring_init(&s_rx_ring);
    bench_port_can_bind(&s_port, &s_rx_ring, &s_can);
    bench_slcan_parser_init(&s_parser);

    for (;;) {
        const uint32_t now_ms = HAL_GetTick();
        uint8_t byte;
        bench_slcan_cmd_t cmd;

        /* Commandes du PC : on ne traite qu'une poignée d'octets par passage. */
        for (uint32_t n = 0u; n < 16u && bench_vcp_read(&byte); n++) {
            if (bench_slcan_feed(&s_parser, byte, &cmd)) {
                execute(&cmd);
            }
        }

        forward_frames(now_ms);
        pump_tx();

        if (s_led_off_ms != 0u && (int32_t)(now_ms - s_led_off_ms) >= 0) {
            HAL_GPIO_WritePin(BENCH_LED_PORT, BENCH_LED_PIN, GPIO_PIN_RESET);
            s_led_off_ms = 0u;
        }
    }
}
