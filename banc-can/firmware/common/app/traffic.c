/**
 * @file traffic.c
 * @brief Trames applicatives périodiques : construction et vérification.
 */

#include "app/traffic.h"

#include <stddef.h>

#include "icd_gen.h"

enum { KIND_ENERGY = 0, KIND_IMU = 1, KIND_TEMP = 2 };

/* Masques tirés de la disposition des signaux dans l'ICD (icd_gen.h) :
 * - ENERGY_COMMAND : octets 0 à 5 (consignes, enable, direction) ; octet 6 =
 *   command_counter, octet 7 = checksum ;
 * - IMU_SPEED : octets 0 à 6 et bits 0-3 de l'octet 7 (wheel_speed) ; bit 4 =
 *   sensor_present, bits 5-7 = frame_counter ;
 * - TEMP_BATTERY : octets 0 à 5 et bits 0-6 de l'octet 6 (state_of_charge) ;
 *   bit 7 = sensor_present, octet 7 = frame_counter. */
static const bench_traffic_desc_t s_desc[BENCH_TRAFFIC_KINDS] = {
    { BENCH_ID_ENERGY_COMMAND, BENCH_ENERGY_COMMAND_DLC, BENCH_SIM_ENERGY_COMMAND_PERIOD_MS,
      BENCH_SIM_ENERGY_COMMAND_STEPS, 8u, true,
      { 0xFFu, 0xFFu, 0xFFu, 0xFFu, 0xFFu, 0xFFu, 0x00u, 0x00u }, 0xFFu, 0u },
    { BENCH_ID_IMU_SPEED, BENCH_IMU_SPEED_DLC, BENCH_SIM_IMU_SPEED_PERIOD_MS,
      BENCH_SIM_IMU_SPEED_STEPS, 3u, false,
      { 0xFFu, 0xFFu, 0xFFu, 0xFFu, 0xFFu, 0xFFu, 0xFFu, 0x0Fu }, 7u, 4u },
    { BENCH_ID_TEMP_BATTERY, BENCH_TEMP_BATTERY_DLC, BENCH_SIM_TEMP_BATTERY_PERIOD_MS,
      BENCH_SIM_TEMP_BATTERY_STEPS, 8u, false,
      { 0xFFu, 0xFFu, 0xFFu, 0xFFu, 0xFFu, 0xFFu, 0x7Fu, 0x00u }, 6u, 7u },
};

const bench_traffic_desc_t *bench_traffic_desc(uint8_t kind) {
    return (kind < BENCH_TRAFFIC_KINDS) ? &s_desc[kind] : NULL;
}

int bench_traffic_kind_of(uint16_t can_id) {
    for (uint8_t k = 0u; k < BENCH_TRAFFIC_KINDS; k++) {
        if (s_desc[k].can_id == can_id) {
            return (int)k;
        }
    }
    return -1;
}

int bench_traffic_kind_of_node(uint8_t node_id) {
    switch (node_id) {
        case 1u:
            return KIND_ENERGY;
        case 2u:
            return KIND_IMU;
        case 3u:
            return KIND_TEMP;
        default:
            return -1;
    }
}

static uint8_t xor_0_6(const uint8_t *data) {
    uint8_t x = 0u;
    for (uint8_t i = 0u; i < 7u; i++) {
        x ^= data[i];
    }
    return x;
}

void bench_traffic_build(uint8_t kind, uint8_t step, uint8_t counter, uint8_t *data) {
    for (uint8_t i = 0u; i < 8u; i++) {
        data[i] = 0u;
    }
    if (kind >= BENCH_TRAFFIC_KINDS) {
        return;
    }
    step = (uint8_t)(step % s_desc[kind].steps);
    const uint8_t mask = (uint8_t)((1u << s_desc[kind].counter_bits) - 1u);

    switch (kind) {
        case KIND_ENERGY: {
            bench_energy_command_t f = bench_sim_energy_command[step];
            f.command_counter = (uint8_t)(counter & mask);
            f.checksum = 0u;
            bench_energy_command_pack(data, &f);
            data[7] = xor_0_6(data);
            break;
        }
        case KIND_IMU: {
            bench_imu_speed_t f = bench_sim_imu_speed[step];
            f.frame_counter = (uint8_t)(counter & mask);
            f.sensor_present = 0u;
            bench_imu_speed_pack(data, &f);
            break;
        }
        default: {
            bench_temp_battery_t f = bench_sim_temp_battery[step];
            f.frame_counter = (uint8_t)(counter & mask);
            f.sensor_present = 0u;
            bench_temp_battery_pack(data, &f);
            break;
        }
    }
}

uint8_t bench_traffic_counter(uint8_t kind, const uint8_t *data) {
    switch (kind) {
        case KIND_ENERGY:
            return data[6];
        case KIND_IMU:
            return (uint8_t)((data[7] >> 5) & 0x07u);
        case KIND_TEMP:
            return data[7];
        default:
            return 0u;
    }
}

bool bench_traffic_checksum_ok(uint8_t kind, const uint8_t *data) {
    if (kind >= BENCH_TRAFFIC_KINDS || !s_desc[kind].has_checksum) {
        return true;
    }
    return data[7] == xor_0_6(data);
}

bool bench_traffic_sensor_present(uint8_t kind, const uint8_t *data) {
    if (kind >= BENCH_TRAFFIC_KINDS || s_desc[kind].sensor_byte == 0xFFu) {
        return false;
    }
    return ((data[s_desc[kind].sensor_byte] >> s_desc[kind].sensor_bit) & 1u) != 0u;
}

int bench_traffic_match_step(uint8_t kind, const uint8_t *data) {
    if (kind >= BENCH_TRAFFIC_KINDS) {
        return -1;
    }
    const bench_traffic_desc_t *d = &s_desc[kind];
    for (uint8_t step = 0u; step < d->steps; step++) {
        uint8_t ref[8];
        bench_traffic_build(kind, step, 0u, ref);
        bool same = true;
        for (uint8_t i = 0u; i < 8u && same; i++) {
            same = ((data[i] ^ ref[i]) & d->content_mask[i]) == 0u;
        }
        if (same) {
            return (int)step;
        }
    }
    return -1;
}
