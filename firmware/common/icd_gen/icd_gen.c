/* ===========================================================================
 *  FICHIER GÉNÉRÉ — NE PAS ÉDITER À LA MAIN
 *
 *  Produit par tools/codegen à partir de icd/bench_icd.yaml.
 *  Toute modification manuelle sera écrasée, et la CI la rejettera.
 *
 *  Regénérer :  python -m tools.codegen
 * ===========================================================================
 */


#include "icd_gen.h"

#include <math.h>
#include <string.h>

/* ---------------------------------------------------------------------
 *  Accès aux champs de bits
 *
 *  Little-endian (Intel) : le bit de départ est le poids faible du signal,
 *  les bits occupent les positions croissantes.
 *  Big-endian (Motorola) : le bit de départ est le poids fort, on descend
 *  dans l'octet puis on poursuit au bit 7 de l'octet suivant.
 *
*  Seules les aides utilisées par l'ICD courant sont générées.
 * ------------------------------------------------------------------- */

static uint64_t bench_load_le(const uint8_t *data, size_t dlc) {
    uint64_t frame = 0u;
    for (size_t i = 0u; i < dlc; i++) {
        frame |= (uint64_t)data[i] << (8u * i);
    }
    return frame;
}

static void bench_store_le(uint8_t *data, size_t dlc, uint64_t frame) {
    for (size_t i = 0u; i < dlc; i++) {
        data[i] = (uint8_t)((frame >> (8u * i)) & 0xFFu);
    }
}

/** Extension de signe d'un champ de @p length bits. */
static int64_t bench_sign_extend(uint64_t raw, unsigned length) {
    const uint64_t sign_bit = (uint64_t)1u << (length - 1u);
    if ((raw & sign_bit) != 0u) {
        return (int64_t)(raw | ~(((uint64_t)1u << length) - 1u));
    }
    return (int64_t)raw;
}

/** Saturation d'une valeur brute sur les bornes du champ. */
static int64_t bench_clamp(int64_t value, int64_t low, int64_t high) {
    if (value < low) {
        return low;
    }
    if (value > high) {
        return high;
    }
    return value;
}

const bench_reserved_range_t bench_bench_reserved_ranges[BENCH_BENCH_RESERVED_COUNT] = {
    { 0x010u, 0x01Fu, "services du banc" },
    { 0x780u, 0x78Fu, "heartbeat des nœuds" },
};

const bench_frame_info_t bench_bench_frames[BENCH_BENCH_FRAME_COUNT] = {
    { 0x010u, 8u, true, false, "ARM" },
    { 0x011u, 8u, true, false, "GO" },
    { 0x012u, 8u, true, false, "BENCH_CFG" },
    { 0x013u, 8u, true, false, "BENCH_RESULT" },
    { 0x781u, 8u, true, false, "HEARTBEAT_N1" },
    { 0x782u, 8u, true, false, "HEARTBEAT_N2" },
    { 0x783u, 8u, true, false, "HEARTBEAT_N3" },
    { 0x784u, 8u, true, false, "HEARTBEAT_N4" },
    { 0x100u, 8u, false, true, "ENERGY_COMMAND" },
    { 0x200u, 8u, false, true, "IMU_SPEED" },
    { 0x300u, 8u, false, true, "TEMP_BATTERY" },
};

const bench_reserved_range_t bench_alt_high_reserved_ranges[BENCH_ALT_HIGH_RESERVED_COUNT] = {
    { 0x020u, 0x02Fu, "services du banc" },
    { 0x790u, 0x79Fu, "heartbeat des nœuds" },
};

const bench_frame_info_t bench_alt_high_frames[BENCH_ALT_HIGH_FRAME_COUNT] = {
    { 0x020u, 8u, true, false, "ARM" },
    { 0x021u, 8u, true, false, "GO" },
    { 0x022u, 8u, true, false, "BENCH_CFG" },
    { 0x023u, 8u, true, false, "BENCH_RESULT" },
    { 0x791u, 8u, true, false, "HEARTBEAT_N1" },
    { 0x792u, 8u, true, false, "HEARTBEAT_N2" },
    { 0x793u, 8u, true, false, "HEARTBEAT_N3" },
    { 0x794u, 8u, true, false, "HEARTBEAT_N4" },
    { 0x100u, 8u, false, true, "ENERGY_COMMAND" },
    { 0x200u, 8u, false, true, "IMU_SPEED" },
    { 0x300u, 8u, false, true, "TEMP_BATTERY" },
};

bool bench_id_is_reserved(uint16_t can_id) {
    for (size_t i = 0u; i < BENCH_BENCH_RESERVED_COUNT; i++) {
        if (can_id >= bench_bench_reserved_ranges[i].first &&
            can_id <= bench_bench_reserved_ranges[i].last) {
            return true;
        }
    }
    return false;
}

const bench_frame_info_t *bench_frame_by_id(uint16_t can_id) {
    for (size_t i = 0u; i < BENCH_BENCH_FRAME_COUNT; i++) {
        if (bench_bench_frames[i].can_id == can_id) {
            return &bench_bench_frames[i];
        }
    }
    return NULL;
}

void bench_bench_cfg_pack(uint8_t *data, const bench_bench_cfg_t *src) {
    uint64_t frame_le = 0u;
    uint64_t frame_be = 0u;
    memset(data, 0, 8u);

    /* target_node */
    {
        int64_t raw = bench_clamp((int64_t)src->target_node, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 0u;
    }
    /* mode */
    {
        int64_t raw = bench_clamp((int64_t)src->mode, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 8u;
    }
    /* param_u16 */
    {
        int64_t raw = bench_clamp((int64_t)src->param_u16, INT64_C(0), INT64_C(65535));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 16u;
    }
    /* duration_ms */
    {
        int64_t raw = bench_clamp((int64_t)src->duration_ms, INT64_C(0), INT64_C(65535));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 32u;
    }
    /* heartbeat_period_ms */
    {
        int64_t raw = bench_clamp((int64_t)src->heartbeat_period_ms, INT64_C(0), INT64_C(65535));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 48u;
    }

    bench_store_le(data, 8u, frame_le);
    (void)frame_be;
}

void bench_bench_cfg_unpack(bench_bench_cfg_t *dst, const uint8_t *data) {
    const uint64_t frame_le = bench_load_le(data, 8u);

    /* target_node */
    {
        uint64_t raw = (frame_le >> 0u) & UINT64_C(0xFF);
        dst->target_node = (uint8_t)((int64_t)raw);
    }
    /* mode */
    {
        uint64_t raw = (frame_le >> 8u) & UINT64_C(0xFF);
        dst->mode = (uint8_t)((int64_t)raw);
    }
    /* param_u16 */
    {
        uint64_t raw = (frame_le >> 16u) & UINT64_C(0xFFFF);
        dst->param_u16 = (uint16_t)((int64_t)raw);
    }
    /* duration_ms */
    {
        uint64_t raw = (frame_le >> 32u) & UINT64_C(0xFFFF);
        dst->duration_ms = (uint16_t)((int64_t)raw);
    }
    /* heartbeat_period_ms */
    {
        uint64_t raw = (frame_le >> 48u) & UINT64_C(0xFFFF);
        dst->heartbeat_period_ms = (uint16_t)((int64_t)raw);
    }
}

void bench_bench_result_pack(uint8_t *data, const bench_bench_result_t *src) {
    uint64_t frame_le = 0u;
    uint64_t frame_be = 0u;
    memset(data, 0, 8u);

    /* node_id */
    {
        int64_t raw = bench_clamp((int64_t)src->node_id, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 0u;
    }
    /* mode */
    {
        int64_t raw = bench_clamp((int64_t)src->mode, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 8u;
    }
    /* status */
    {
        int64_t raw = bench_clamp((int64_t)src->status, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 16u;
    }
    /* arm_rx */
    {
        int64_t raw = bench_clamp((int64_t)src->arm_rx, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 24u;
    }
    /* frames_sent */
    {
        int64_t raw = bench_clamp((int64_t)src->frames_sent, INT64_C(0), INT64_C(65535));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 32u;
    }
    /* frames_lost */
    {
        int64_t raw = bench_clamp((int64_t)src->frames_lost, INT64_C(0), INT64_C(65535));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 48u;
    }

    bench_store_le(data, 8u, frame_le);
    (void)frame_be;
}

void bench_bench_result_unpack(bench_bench_result_t *dst, const uint8_t *data) {
    const uint64_t frame_le = bench_load_le(data, 8u);

    /* node_id */
    {
        uint64_t raw = (frame_le >> 0u) & UINT64_C(0xFF);
        dst->node_id = (uint8_t)((int64_t)raw);
    }
    /* mode */
    {
        uint64_t raw = (frame_le >> 8u) & UINT64_C(0xFF);
        dst->mode = (uint8_t)((int64_t)raw);
    }
    /* status */
    {
        uint64_t raw = (frame_le >> 16u) & UINT64_C(0xFF);
        dst->status = (uint8_t)((int64_t)raw);
    }
    /* arm_rx */
    {
        uint64_t raw = (frame_le >> 24u) & UINT64_C(0xFF);
        dst->arm_rx = (uint8_t)((int64_t)raw);
    }
    /* frames_sent */
    {
        uint64_t raw = (frame_le >> 32u) & UINT64_C(0xFFFF);
        dst->frames_sent = (uint16_t)((int64_t)raw);
    }
    /* frames_lost */
    {
        uint64_t raw = (frame_le >> 48u) & UINT64_C(0xFFFF);
        dst->frames_lost = (uint16_t)((int64_t)raw);
    }
}

void bench_heartbeat_pack(uint8_t *data, const bench_heartbeat_t *src) {
    uint64_t frame_le = 0u;
    uint64_t frame_be = 0u;
    memset(data, 0, 8u);

    /* ctrl_state */
    {
        int64_t raw = bench_clamp((int64_t)src->ctrl_state, INT64_C(0), INT64_C(3));
        frame_le |= ((uint64_t)raw & UINT64_C(0x3)) << 0u;
    }
    /* last_error_code */
    {
        int64_t raw = bench_clamp((int64_t)src->last_error_code, INT64_C(0), INT64_C(7));
        frame_le |= ((uint64_t)raw & UINT64_C(0x7)) << 2u;
    }
    /* clock_not_qualified */
    {
        int64_t raw = bench_clamp((int64_t)src->clock_not_qualified, INT64_C(0), INT64_C(1));
        frame_le |= ((uint64_t)raw & UINT64_C(0x1)) << 5u;
    }
    /* fault_mode_active */
    {
        int64_t raw = bench_clamp((int64_t)src->fault_mode_active, INT64_C(0), INT64_C(1));
        frame_le |= ((uint64_t)raw & UINT64_C(0x1)) << 6u;
    }
    /* silent_mode */
    {
        int64_t raw = bench_clamp((int64_t)src->silent_mode, INT64_C(0), INT64_C(1));
        frame_le |= ((uint64_t)raw & UINT64_C(0x1)) << 7u;
    }
    /* tec */
    {
        int64_t raw = bench_clamp((int64_t)src->tec, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 8u;
    }
    /* rec */
    {
        int64_t raw = bench_clamp((int64_t)src->rec, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 16u;
    }
    /* current_mode */
    {
        int64_t raw = bench_clamp((int64_t)src->current_mode, INT64_C(0), INT64_C(15));
        frame_le |= ((uint64_t)raw & UINT64_C(0xF)) << 24u;
    }
    /* reserved */
    {
        int64_t raw = bench_clamp((int64_t)src->reserved, INT64_C(0), INT64_C(15));
        frame_le |= ((uint64_t)raw & UINT64_C(0xF)) << 28u;
    }
    /* rx_fifo_lost */
    {
        int64_t raw = bench_clamp((int64_t)src->rx_fifo_lost, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 32u;
    }
    /* ring_overflow */
    {
        int64_t raw = bench_clamp((int64_t)src->ring_overflow, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 40u;
    }
    /* non_classic_rx */
    {
        int64_t raw = bench_clamp((int64_t)src->non_classic_rx, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 48u;
    }
    /* ext_id_rx */
    {
        int64_t raw = bench_clamp((int64_t)src->ext_id_rx, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 56u;
    }

    bench_store_le(data, 8u, frame_le);
    (void)frame_be;
}

void bench_heartbeat_unpack(bench_heartbeat_t *dst, const uint8_t *data) {
    const uint64_t frame_le = bench_load_le(data, 8u);

    /* ctrl_state */
    {
        uint64_t raw = (frame_le >> 0u) & UINT64_C(0x3);
        dst->ctrl_state = (uint8_t)((int64_t)raw);
    }
    /* last_error_code */
    {
        uint64_t raw = (frame_le >> 2u) & UINT64_C(0x7);
        dst->last_error_code = (uint8_t)((int64_t)raw);
    }
    /* clock_not_qualified */
    {
        uint64_t raw = (frame_le >> 5u) & UINT64_C(0x1);
        dst->clock_not_qualified = (uint8_t)((int64_t)raw);
    }
    /* fault_mode_active */
    {
        uint64_t raw = (frame_le >> 6u) & UINT64_C(0x1);
        dst->fault_mode_active = (uint8_t)((int64_t)raw);
    }
    /* silent_mode */
    {
        uint64_t raw = (frame_le >> 7u) & UINT64_C(0x1);
        dst->silent_mode = (uint8_t)((int64_t)raw);
    }
    /* tec */
    {
        uint64_t raw = (frame_le >> 8u) & UINT64_C(0xFF);
        dst->tec = (uint8_t)((int64_t)raw);
    }
    /* rec */
    {
        uint64_t raw = (frame_le >> 16u) & UINT64_C(0xFF);
        dst->rec = (uint8_t)((int64_t)raw);
    }
    /* current_mode */
    {
        uint64_t raw = (frame_le >> 24u) & UINT64_C(0xF);
        dst->current_mode = (uint8_t)((int64_t)raw);
    }
    /* reserved */
    {
        uint64_t raw = (frame_le >> 28u) & UINT64_C(0xF);
        dst->reserved = (uint8_t)((int64_t)raw);
    }
    /* rx_fifo_lost */
    {
        uint64_t raw = (frame_le >> 32u) & UINT64_C(0xFF);
        dst->rx_fifo_lost = (uint8_t)((int64_t)raw);
    }
    /* ring_overflow */
    {
        uint64_t raw = (frame_le >> 40u) & UINT64_C(0xFF);
        dst->ring_overflow = (uint8_t)((int64_t)raw);
    }
    /* non_classic_rx */
    {
        uint64_t raw = (frame_le >> 48u) & UINT64_C(0xFF);
        dst->non_classic_rx = (uint8_t)((int64_t)raw);
    }
    /* ext_id_rx */
    {
        uint64_t raw = (frame_le >> 56u) & UINT64_C(0xFF);
        dst->ext_id_rx = (uint8_t)((int64_t)raw);
    }
}

void bench_energy_command_pack(uint8_t *data, const bench_energy_command_t *src) {
    uint64_t frame_le = 0u;
    uint64_t frame_be = 0u;
    memset(data, 0, 8u);

    /* torque_setpoint */
    {
        int64_t raw = bench_clamp((int64_t)llround(((double)src->torque_setpoint - (0)) / (0.10000000000000001)), INT64_C(-32768), INT64_C(32767));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 0u;
    }
    /* speed_setpoint */
    {
        int64_t raw = bench_clamp((int64_t)llround(((double)src->speed_setpoint - (0)) / (0.5)), INT64_C(-32768), INT64_C(32767));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 16u;
    }
    /* current_limit */
    {
        int64_t raw = bench_clamp((int64_t)llround(((double)src->current_limit - (0)) / (0.050000000000000003)), INT64_C(0), INT64_C(4095));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFF)) << 32u;
    }
    /* enable */
    {
        int64_t raw = bench_clamp((int64_t)src->enable, INT64_C(0), INT64_C(1));
        frame_le |= ((uint64_t)raw & UINT64_C(0x1)) << 44u;
    }
    /* direction */
    {
        int64_t raw = bench_clamp((int64_t)src->direction, INT64_C(0), INT64_C(1));
        frame_le |= ((uint64_t)raw & UINT64_C(0x1)) << 45u;
    }
    /* command_counter */
    {
        int64_t raw = bench_clamp((int64_t)src->command_counter, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 48u;
    }
    /* checksum */
    {
        int64_t raw = bench_clamp((int64_t)src->checksum, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 56u;
    }

    bench_store_le(data, 8u, frame_le);
    (void)frame_be;
}

void bench_energy_command_unpack(bench_energy_command_t *dst, const uint8_t *data) {
    const uint64_t frame_le = bench_load_le(data, 8u);

    /* torque_setpoint */
    {
        uint64_t raw = (frame_le >> 0u) & UINT64_C(0xFFFF);
        dst->torque_setpoint = (float)((double)(bench_sign_extend(raw, 16u)) * 0.10000000000000001 + 0);
    }
    /* speed_setpoint */
    {
        uint64_t raw = (frame_le >> 16u) & UINT64_C(0xFFFF);
        dst->speed_setpoint = (float)((double)(bench_sign_extend(raw, 16u)) * 0.5 + 0);
    }
    /* current_limit */
    {
        uint64_t raw = (frame_le >> 32u) & UINT64_C(0xFFF);
        dst->current_limit = (float)((double)((int64_t)raw) * 0.050000000000000003 + 0);
    }
    /* enable */
    {
        uint64_t raw = (frame_le >> 44u) & UINT64_C(0x1);
        dst->enable = (uint8_t)((int64_t)raw);
    }
    /* direction */
    {
        uint64_t raw = (frame_le >> 45u) & UINT64_C(0x1);
        dst->direction = (uint8_t)((int64_t)raw);
    }
    /* command_counter */
    {
        uint64_t raw = (frame_le >> 48u) & UINT64_C(0xFF);
        dst->command_counter = (uint8_t)((int64_t)raw);
    }
    /* checksum */
    {
        uint64_t raw = (frame_le >> 56u) & UINT64_C(0xFF);
        dst->checksum = (uint8_t)((int64_t)raw);
    }
}

void bench_imu_speed_pack(uint8_t *data, const bench_imu_speed_t *src) {
    uint64_t frame_le = 0u;
    uint64_t frame_be = 0u;
    memset(data, 0, 8u);

    /* accel_x */
    {
        int64_t raw = bench_clamp((int64_t)llround(((double)src->accel_x - (0)) / (0.001)), INT64_C(-32768), INT64_C(32767));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 0u;
    }
    /* accel_y */
    {
        int64_t raw = bench_clamp((int64_t)llround(((double)src->accel_y - (0)) / (0.001)), INT64_C(-32768), INT64_C(32767));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 16u;
    }
    /* gyro_z */
    {
        int64_t raw = bench_clamp((int64_t)llround(((double)src->gyro_z - (0)) / (0.0625)), INT64_C(-32768), INT64_C(32767));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 32u;
    }
    /* wheel_speed */
    {
        int64_t raw = bench_clamp((int64_t)llround(((double)src->wheel_speed - (0)) / (0.25)), INT64_C(0), INT64_C(4095));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFF)) << 48u;
    }
    /* sensor_present */
    {
        int64_t raw = bench_clamp((int64_t)src->sensor_present, INT64_C(0), INT64_C(1));
        frame_le |= ((uint64_t)raw & UINT64_C(0x1)) << 60u;
    }
    /* frame_counter */
    {
        int64_t raw = bench_clamp((int64_t)src->frame_counter, INT64_C(0), INT64_C(7));
        frame_le |= ((uint64_t)raw & UINT64_C(0x7)) << 61u;
    }

    bench_store_le(data, 8u, frame_le);
    (void)frame_be;
}

void bench_imu_speed_unpack(bench_imu_speed_t *dst, const uint8_t *data) {
    const uint64_t frame_le = bench_load_le(data, 8u);

    /* accel_x */
    {
        uint64_t raw = (frame_le >> 0u) & UINT64_C(0xFFFF);
        dst->accel_x = (float)((double)(bench_sign_extend(raw, 16u)) * 0.001 + 0);
    }
    /* accel_y */
    {
        uint64_t raw = (frame_le >> 16u) & UINT64_C(0xFFFF);
        dst->accel_y = (float)((double)(bench_sign_extend(raw, 16u)) * 0.001 + 0);
    }
    /* gyro_z */
    {
        uint64_t raw = (frame_le >> 32u) & UINT64_C(0xFFFF);
        dst->gyro_z = (float)((double)(bench_sign_extend(raw, 16u)) * 0.0625 + 0);
    }
    /* wheel_speed */
    {
        uint64_t raw = (frame_le >> 48u) & UINT64_C(0xFFF);
        dst->wheel_speed = (float)((double)((int64_t)raw) * 0.25 + 0);
    }
    /* sensor_present */
    {
        uint64_t raw = (frame_le >> 60u) & UINT64_C(0x1);
        dst->sensor_present = (uint8_t)((int64_t)raw);
    }
    /* frame_counter */
    {
        uint64_t raw = (frame_le >> 61u) & UINT64_C(0x7);
        dst->frame_counter = (uint8_t)((int64_t)raw);
    }
}

void bench_temp_battery_pack(uint8_t *data, const bench_temp_battery_t *src) {
    uint64_t frame_le = 0u;
    uint64_t frame_be = 0u;
    memset(data, 0, 8u);

    /* temperature */
    {
        int64_t raw = bench_clamp((int64_t)llround(((double)src->temperature - (0)) / (0.0625)), INT64_C(-32768), INT64_C(32767));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 0u;
    }
    /* pack_voltage */
    {
        int64_t raw = bench_clamp((int64_t)llround(((double)src->pack_voltage - (0)) / (0.01)), INT64_C(0), INT64_C(65535));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 16u;
    }
    /* pack_current */
    {
        int64_t raw = bench_clamp((int64_t)llround(((double)src->pack_current - (0)) / (0.01)), INT64_C(-32768), INT64_C(32767));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFFFF)) << 32u;
    }
    /* state_of_charge */
    {
        int64_t raw = bench_clamp((int64_t)src->state_of_charge, INT64_C(0), INT64_C(127));
        frame_le |= ((uint64_t)raw & UINT64_C(0x7F)) << 48u;
    }
    /* sensor_present */
    {
        int64_t raw = bench_clamp((int64_t)src->sensor_present, INT64_C(0), INT64_C(1));
        frame_le |= ((uint64_t)raw & UINT64_C(0x1)) << 55u;
    }
    /* frame_counter */
    {
        int64_t raw = bench_clamp((int64_t)src->frame_counter, INT64_C(0), INT64_C(255));
        frame_le |= ((uint64_t)raw & UINT64_C(0xFF)) << 56u;
    }

    bench_store_le(data, 8u, frame_le);
    (void)frame_be;
}

void bench_temp_battery_unpack(bench_temp_battery_t *dst, const uint8_t *data) {
    const uint64_t frame_le = bench_load_le(data, 8u);

    /* temperature */
    {
        uint64_t raw = (frame_le >> 0u) & UINT64_C(0xFFFF);
        dst->temperature = (float)((double)(bench_sign_extend(raw, 16u)) * 0.0625 + 0);
    }
    /* pack_voltage */
    {
        uint64_t raw = (frame_le >> 16u) & UINT64_C(0xFFFF);
        dst->pack_voltage = (float)((double)((int64_t)raw) * 0.01 + 0);
    }
    /* pack_current */
    {
        uint64_t raw = (frame_le >> 32u) & UINT64_C(0xFFFF);
        dst->pack_current = (float)((double)(bench_sign_extend(raw, 16u)) * 0.01 + 0);
    }
    /* state_of_charge */
    {
        uint64_t raw = (frame_le >> 48u) & UINT64_C(0x7F);
        dst->state_of_charge = (uint8_t)((int64_t)raw);
    }
    /* sensor_present */
    {
        uint64_t raw = (frame_le >> 55u) & UINT64_C(0x1);
        dst->sensor_present = (uint8_t)((int64_t)raw);
    }
    /* frame_counter */
    {
        uint64_t raw = (frame_le >> 56u) & UINT64_C(0xFF);
        dst->frame_counter = (uint8_t)((int64_t)raw);
    }
}
