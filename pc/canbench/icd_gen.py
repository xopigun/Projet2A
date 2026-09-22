"""FICHIER GÉNÉRÉ — NE PAS ÉDITER À LA MAIN.

Produit par tools/codegen à partir de icd/bench_icd.yaml.
Toute modification manuelle sera écrasée, et la CI la rejettera.

Regénérer :  python -m tools.codegen
"""


from __future__ import annotations

import math
from dataclasses import dataclass, field


def bench_round(value: float) -> int:
    """Arrondit à l'entier le plus proche, les demis s'éloignant de zéro.

    Convention imposée par ``llround()`` dans le code C généré : ``round()`` de
    Python arrondit au pair et casserait la parité C <-> Python.
    """
    return int(math.floor(value + 0.5)) if value >= 0 else int(math.ceil(value - 0.5))


def _sign_extend(raw: int, length: int) -> int:
    return raw - (1 << length) if raw >= (1 << (length - 1)) else raw


def _clamp(value: int, low: int, high: int) -> int:
    return low if value < low else high if value > high else value


BITRATE = 500000
DEFAULT_PROFILE = 'bench'

#: Identifiants par profil réseau : PROFILES[<profil>]['ids'][<trame>].
PROFILES = {
    'bench': {
        'description': 'Profil par défaut du banc. Les identifiants de service y sont déclarés « réservés banc, reconfigurables » dans les ICD partenaires, jamais imposés.',
        'heartbeat_base': 0x780,
        'ids': {
            'ARM': 0x010,
            'GO': 0x011,
            'BENCH_CFG': 0x012,
            'BENCH_RESULT': 0x013,
            'HEARTBEAT_N1': 0x781,
            'HEARTBEAT_N2': 0x782,
            'HEARTBEAT_N3': 0x783,
            'HEARTBEAT_N4': 0x784,
            'ENERGY_COMMAND': 0x100,
            'IMU_SPEED': 0x200,
            'TEMP_BATTERY': 0x300,
        },
        'reserved_ranges': [
            (0x010, 0x01F, 'services du banc'),
            (0x780, 0x78F, 'heartbeat des nœuds'),
        ],
    },
    'alt_high': {
        'description': 'Profil alternatif, services et heartbeat décalés vers le haut.',
        'heartbeat_base': 0x790,
        'ids': {
            'ARM': 0x020,
            'GO': 0x021,
            'BENCH_CFG': 0x022,
            'BENCH_RESULT': 0x023,
            'HEARTBEAT_N1': 0x791,
            'HEARTBEAT_N2': 0x792,
            'HEARTBEAT_N3': 0x793,
            'HEARTBEAT_N4': 0x794,
            'ENERGY_COMMAND': 0x100,
            'IMU_SPEED': 0x200,
            'TEMP_BATTERY': 0x300,
        },
        'reserved_ranges': [
            (0x020, 0x02F, 'services du banc'),
            (0x790, 0x79F, 'heartbeat des nœuds'),
        ],
    },
}

#: Raccourcis vers le profil par défaut.
IDS = PROFILES[DEFAULT_PROFILE]['ids']

#: Description des nœuds déclarés dans l'ICD.
NODES = [
    {'node_id': 1, 'name': 'N1', 'board': 'nucleo_g431kb', 'role': 'energy_command', 'contender': True},
    {'node_id': 2, 'name': 'N2', 'board': 'nucleo_g431kb', 'role': 'imu_speed', 'contender': True},
    {'node_id': 3, 'name': 'N3', 'board': 'nucleo_g431kb', 'role': 'temp_battery', 'contender': True},
    {'node_id': 4, 'name': 'N4', 'board': 'bluepill_f103', 'role': 'faulty', 'contender': False},
]

#: Trames contendantes du test d'arbitrage, par priorité croissante d'identifiant.
CONTENDERS = [
    {'name': 'ENERGY_COMMAND', 'can_id': 0x100, 'sender': 'N1'},
    {'name': 'IMU_SPEED', 'can_id': 0x200, 'sender': 'N2'},
    {'name': 'TEMP_BATTERY', 'can_id': 0x300, 'sender': 'N3'},
]

#: Métadonnées de chaque trame, utilisées par le décodage générique.
FRAMES = {
    0x010: {
        'name': 'ARM',
        'layout': 'ARM',
        'dlc': 8,
        'kind': 'service',
        'sender': 'PC',
        'period_ms': None,
        'contender': False,
        'signals': [
        ],
    },
    0x011: {
        'name': 'GO',
        'layout': 'GO',
        'dlc': 8,
        'kind': 'service',
        'sender': 'PC',
        'period_ms': None,
        'contender': False,
        'signals': [
        ],
    },
    0x012: {
        'name': 'BENCH_CFG',
        'layout': 'BENCH_CFG',
        'dlc': 8,
        'kind': 'service',
        'sender': 'PC',
        'period_ms': None,
        'contender': False,
        'signals': [
        {'name': 'target_node', 'start_byte': 0, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'mode', 'start_byte': 1, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'param_u16', 'start_byte': 2, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 65535.0, 'default': 0.0},
        {'name': 'duration_ms', 'start_byte': 4, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': 'ms', 'min': 0.0, 'max': 65535.0, 'default': 1000.0},
        {'name': 'heartbeat_period_ms', 'start_byte': 6, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': 'ms', 'min': 0.0, 'max': 65535.0, 'default': 500.0},
        ],
    },
    0x013: {
        'name': 'BENCH_RESULT',
        'layout': 'BENCH_RESULT',
        'dlc': 8,
        'kind': 'service',
        'sender': 'any_node',
        'period_ms': None,
        'contender': False,
        'signals': [
        {'name': 'node_id', 'start_byte': 0, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'mode', 'start_byte': 1, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'status', 'start_byte': 2, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'arm_rx', 'start_byte': 3, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'frames_sent', 'start_byte': 4, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 65535.0, 'default': 0.0},
        {'name': 'frames_lost', 'start_byte': 6, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 65535.0, 'default': 0.0},
        ],
    },
    0x781: {
        'name': 'HEARTBEAT_N1',
        'layout': 'HEARTBEAT',
        'dlc': 8,
        'kind': 'service',
        'sender': 'self',
        'period_ms': None,
        'contender': False,
        'signals': [
        {'name': 'ctrl_state', 'start_byte': 0, 'start_bit': 0, 'length': 2, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 3.0, 'default': 0.0},
        {'name': 'last_error_code', 'start_byte': 0, 'start_bit': 2, 'length': 3, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 7.0, 'default': 0.0},
        {'name': 'clock_not_qualified', 'start_byte': 0, 'start_bit': 5, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'fault_mode_active', 'start_byte': 0, 'start_bit': 6, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'silent_mode', 'start_byte': 0, 'start_bit': 7, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'tec', 'start_byte': 1, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'rec', 'start_byte': 2, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'current_mode', 'start_byte': 3, 'start_bit': 0, 'length': 4, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 15.0, 'default': 0.0},
        {'name': 'reserved', 'start_byte': 3, 'start_bit': 4, 'length': 4, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 15.0, 'default': 0.0},
        {'name': 'rx_fifo_lost', 'start_byte': 4, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'ring_overflow', 'start_byte': 5, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'non_classic_rx', 'start_byte': 6, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'ext_id_rx', 'start_byte': 7, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        ],
    },
    0x782: {
        'name': 'HEARTBEAT_N2',
        'layout': 'HEARTBEAT',
        'dlc': 8,
        'kind': 'service',
        'sender': 'self',
        'period_ms': None,
        'contender': False,
        'signals': [
        {'name': 'ctrl_state', 'start_byte': 0, 'start_bit': 0, 'length': 2, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 3.0, 'default': 0.0},
        {'name': 'last_error_code', 'start_byte': 0, 'start_bit': 2, 'length': 3, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 7.0, 'default': 0.0},
        {'name': 'clock_not_qualified', 'start_byte': 0, 'start_bit': 5, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'fault_mode_active', 'start_byte': 0, 'start_bit': 6, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'silent_mode', 'start_byte': 0, 'start_bit': 7, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'tec', 'start_byte': 1, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'rec', 'start_byte': 2, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'current_mode', 'start_byte': 3, 'start_bit': 0, 'length': 4, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 15.0, 'default': 0.0},
        {'name': 'reserved', 'start_byte': 3, 'start_bit': 4, 'length': 4, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 15.0, 'default': 0.0},
        {'name': 'rx_fifo_lost', 'start_byte': 4, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'ring_overflow', 'start_byte': 5, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'non_classic_rx', 'start_byte': 6, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'ext_id_rx', 'start_byte': 7, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        ],
    },
    0x783: {
        'name': 'HEARTBEAT_N3',
        'layout': 'HEARTBEAT',
        'dlc': 8,
        'kind': 'service',
        'sender': 'self',
        'period_ms': None,
        'contender': False,
        'signals': [
        {'name': 'ctrl_state', 'start_byte': 0, 'start_bit': 0, 'length': 2, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 3.0, 'default': 0.0},
        {'name': 'last_error_code', 'start_byte': 0, 'start_bit': 2, 'length': 3, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 7.0, 'default': 0.0},
        {'name': 'clock_not_qualified', 'start_byte': 0, 'start_bit': 5, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'fault_mode_active', 'start_byte': 0, 'start_bit': 6, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'silent_mode', 'start_byte': 0, 'start_bit': 7, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'tec', 'start_byte': 1, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'rec', 'start_byte': 2, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'current_mode', 'start_byte': 3, 'start_bit': 0, 'length': 4, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 15.0, 'default': 0.0},
        {'name': 'reserved', 'start_byte': 3, 'start_bit': 4, 'length': 4, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 15.0, 'default': 0.0},
        {'name': 'rx_fifo_lost', 'start_byte': 4, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'ring_overflow', 'start_byte': 5, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'non_classic_rx', 'start_byte': 6, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'ext_id_rx', 'start_byte': 7, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        ],
    },
    0x784: {
        'name': 'HEARTBEAT_N4',
        'layout': 'HEARTBEAT',
        'dlc': 8,
        'kind': 'service',
        'sender': 'self',
        'period_ms': None,
        'contender': False,
        'signals': [
        {'name': 'ctrl_state', 'start_byte': 0, 'start_bit': 0, 'length': 2, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 3.0, 'default': 0.0},
        {'name': 'last_error_code', 'start_byte': 0, 'start_bit': 2, 'length': 3, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 7.0, 'default': 0.0},
        {'name': 'clock_not_qualified', 'start_byte': 0, 'start_bit': 5, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'fault_mode_active', 'start_byte': 0, 'start_bit': 6, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'silent_mode', 'start_byte': 0, 'start_bit': 7, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'tec', 'start_byte': 1, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'rec', 'start_byte': 2, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'current_mode', 'start_byte': 3, 'start_bit': 0, 'length': 4, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 15.0, 'default': 0.0},
        {'name': 'reserved', 'start_byte': 3, 'start_bit': 4, 'length': 4, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 15.0, 'default': 0.0},
        {'name': 'rx_fifo_lost', 'start_byte': 4, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'ring_overflow', 'start_byte': 5, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'non_classic_rx', 'start_byte': 6, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'ext_id_rx', 'start_byte': 7, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        ],
    },
    0x100: {
        'name': 'ENERGY_COMMAND',
        'layout': 'ENERGY_COMMAND',
        'dlc': 8,
        'kind': 'application',
        'sender': 'N1',
        'period_ms': 20,
        'contender': True,
        'signals': [
        {'name': 'torque_setpoint', 'start_byte': 0, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': True, 'factor': 0.1, 'offset': 0.0, 'unit': 'N.m', 'min': -3276.8, 'max': 3276.7, 'default': 0.0},
        {'name': 'speed_setpoint', 'start_byte': 2, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': True, 'factor': 0.5, 'offset': 0.0, 'unit': 'rpm', 'min': -16384.0, 'max': 16383.5, 'default': 0.0},
        {'name': 'current_limit', 'start_byte': 4, 'start_bit': 0, 'length': 12, 'byte_order': 'little_endian', 'signed': False, 'factor': 0.05, 'offset': 0.0, 'unit': 'A', 'min': 0.0, 'max': 204.75, 'default': 0.0},
        {'name': 'enable', 'start_byte': 5, 'start_bit': 4, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'direction', 'start_byte': 5, 'start_bit': 5, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'command_counter', 'start_byte': 6, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        {'name': 'checksum', 'start_byte': 7, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        ],
    },
    0x200: {
        'name': 'IMU_SPEED',
        'layout': 'IMU_SPEED',
        'dlc': 8,
        'kind': 'application',
        'sender': 'N2',
        'period_ms': 20,
        'contender': True,
        'signals': [
        {'name': 'accel_x', 'start_byte': 0, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': True, 'factor': 0.001, 'offset': 0.0, 'unit': 'g', 'min': -32.768, 'max': 32.767, 'default': 0.0},
        {'name': 'accel_y', 'start_byte': 2, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': True, 'factor': 0.001, 'offset': 0.0, 'unit': 'g', 'min': -32.768, 'max': 32.767, 'default': 0.0},
        {'name': 'gyro_z', 'start_byte': 4, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': True, 'factor': 0.0625, 'offset': 0.0, 'unit': 'deg/s', 'min': -2048.0, 'max': 2047.9375, 'default': 0.0},
        {'name': 'wheel_speed', 'start_byte': 6, 'start_bit': 0, 'length': 12, 'byte_order': 'little_endian', 'signed': False, 'factor': 0.25, 'offset': 0.0, 'unit': 'km/h', 'min': 0.0, 'max': 1023.75, 'default': 0.0},
        {'name': 'sensor_present', 'start_byte': 7, 'start_bit': 4, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'frame_counter', 'start_byte': 7, 'start_bit': 5, 'length': 3, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 7.0, 'default': 0.0},
        ],
    },
    0x300: {
        'name': 'TEMP_BATTERY',
        'layout': 'TEMP_BATTERY',
        'dlc': 8,
        'kind': 'application',
        'sender': 'N3',
        'period_ms': 20,
        'contender': True,
        'signals': [
        {'name': 'temperature', 'start_byte': 0, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': True, 'factor': 0.0625, 'offset': 0.0, 'unit': 'degC', 'min': -55.0, 'max': 125.0, 'default': 20.0},
        {'name': 'pack_voltage', 'start_byte': 2, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': False, 'factor': 0.01, 'offset': 0.0, 'unit': 'V', 'min': 0.0, 'max': 655.35, 'default': 0.0},
        {'name': 'pack_current', 'start_byte': 4, 'start_bit': 0, 'length': 16, 'byte_order': 'little_endian', 'signed': True, 'factor': 0.01, 'offset': 0.0, 'unit': 'A', 'min': -327.68, 'max': 327.67, 'default': 0.0},
        {'name': 'state_of_charge', 'start_byte': 6, 'start_bit': 0, 'length': 7, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '%', 'min': 0.0, 'max': 100.0, 'default': 0.0},
        {'name': 'sensor_present', 'start_byte': 6, 'start_bit': 7, 'length': 1, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 1.0, 'default': 0.0},
        {'name': 'frame_counter', 'start_byte': 7, 'start_bit': 0, 'length': 8, 'byte_order': 'little_endian', 'signed': False, 'factor': 1.0, 'offset': 0.0, 'unit': '', 'min': 0.0, 'max': 255.0, 'default': 0.0},
        ],
    },
}

#: Séquences déterministes des simulateurs de capteurs.
SIMULATIONS = {
    'IMU_SPEED': {
        'period_ms': 20,
        'steps': [
            {'accel_x': 0.0, 'accel_y': 0.0, 'gyro_z': 0.0, 'wheel_speed': 0.0},
            {'accel_x': 0.25, 'accel_y': -0.125, 'gyro_z': 90.0, 'wheel_speed': 12.5},
            {'accel_x': 1.0, 'accel_y': 0.5, 'gyro_z': -180.0, 'wheel_speed': 25.0},
            {'accel_x': -1.0, 'accel_y': 0.75, 'gyro_z': 360.0, 'wheel_speed': 50.75},
            {'accel_x': 32.767, 'accel_y': -32.768, 'gyro_z': 2047.9375, 'wheel_speed': 1023.75},
            {'accel_x': -32.768, 'accel_y': 32.767, 'gyro_z': -2048.0, 'wheel_speed': 0.25},
        ],
    },
    'TEMP_BATTERY': {
        'period_ms': 20,
        'steps': [
            {'temperature': 20.0, 'pack_voltage': 0.0, 'pack_current': 0.0, 'state_of_charge': 100},
            {'temperature': 0.0, 'pack_voltage': 48.0, 'pack_current': 12.5, 'state_of_charge': 75},
            {'temperature': -55.0, 'pack_voltage': 12.34, 'pack_current': -327.68, 'state_of_charge': 0},
            {'temperature': 125.0, 'pack_voltage': 655.35, 'pack_current': 327.67, 'state_of_charge': 50},
            {'temperature': 36.6875, 'pack_voltage': 24.01, 'pack_current': -0.01, 'state_of_charge': 1},
        ],
    },
    'ENERGY_COMMAND': {
        'period_ms': 20,
        'steps': [
            {'torque_setpoint': 0.0, 'speed_setpoint': 0.0, 'current_limit': 0.0, 'enable': 0, 'direction': 0},
            {'torque_setpoint': 12.5, 'speed_setpoint': 1500.0, 'current_limit': 10.0, 'enable': 1, 'direction': 0},
            {'torque_setpoint': -12.5, 'speed_setpoint': -1500.0, 'current_limit': 10.0, 'enable': 1, 'direction': 1},
            {'torque_setpoint': 3276.7, 'speed_setpoint': 16383.5, 'current_limit': 204.75, 'enable': 1, 'direction': 0},
            {'torque_setpoint': -3276.8, 'speed_setpoint': -16384.0, 'current_limit': 0.05, 'enable': 0, 'direction': 1},
        ],
    },
}


@dataclass
class BenchCfg:
    """Commande de configuration d'un nœud pendant un test."""

    DLC = 8

    target_node: int = 0.0
    mode: int = 0.0
    param_u16: int = 0.0
    duration_ms: int = 1000.0
    heartbeat_period_ms: int = 500.0

    def pack(self) -> bytes:
        frame_le = 0
        frame_be = 0
        raw = _clamp(int(self.target_node), 0, 255)
        frame_le |= (raw & 0xFF) << 0
        raw = _clamp(int(self.mode), 0, 255)
        frame_le |= (raw & 0xFF) << 8
        raw = _clamp(int(self.param_u16), 0, 65535)
        frame_le |= (raw & 0xFFFF) << 16
        raw = _clamp(int(self.duration_ms), 0, 65535)
        frame_le |= (raw & 0xFFFF) << 32
        raw = _clamp(int(self.heartbeat_period_ms), 0, 65535)
        frame_le |= (raw & 0xFFFF) << 48
        data = bytearray(frame_le.to_bytes(8, 'little'))
        if frame_be:
            be = frame_be.to_bytes(8, 'big')
            data = bytearray(a | b for a, b in zip(data, be))
        return bytes(data)

    @classmethod
    def unpack(cls, data: bytes):
        if len(data) != 8:
            raise ValueError(f'BENCH_CFG : {len(data)} octets reçus, 8 attendus')
        frame_le = int.from_bytes(data, 'little')
        frame_be = int.from_bytes(data, 'big')
        return cls(
            target_node=(frame_le >> 0) & 0xFF,
            mode=(frame_le >> 8) & 0xFF,
            param_u16=(frame_le >> 16) & 0xFFFF,
            duration_ms=(frame_le >> 32) & 0xFFFF,
            heartbeat_period_ms=(frame_le >> 48) & 0xFFFF,
        )

@dataclass
class BenchResult:
    """Réponse de fin de test émise par le nœud visé."""

    DLC = 8

    node_id: int = 0.0
    mode: int = 0.0
    status: int = 0.0
    arm_rx: int = 0.0
    frames_sent: int = 0.0
    frames_lost: int = 0.0

    def pack(self) -> bytes:
        frame_le = 0
        frame_be = 0
        raw = _clamp(int(self.node_id), 0, 255)
        frame_le |= (raw & 0xFF) << 0
        raw = _clamp(int(self.mode), 0, 255)
        frame_le |= (raw & 0xFF) << 8
        raw = _clamp(int(self.status), 0, 255)
        frame_le |= (raw & 0xFF) << 16
        raw = _clamp(int(self.arm_rx), 0, 255)
        frame_le |= (raw & 0xFF) << 24
        raw = _clamp(int(self.frames_sent), 0, 65535)
        frame_le |= (raw & 0xFFFF) << 32
        raw = _clamp(int(self.frames_lost), 0, 65535)
        frame_le |= (raw & 0xFFFF) << 48
        data = bytearray(frame_le.to_bytes(8, 'little'))
        if frame_be:
            be = frame_be.to_bytes(8, 'big')
            data = bytearray(a | b for a, b in zip(data, be))
        return bytes(data)

    @classmethod
    def unpack(cls, data: bytes):
        if len(data) != 8:
            raise ValueError(f'BENCH_RESULT : {len(data)} octets reçus, 8 attendus')
        frame_le = int.from_bytes(data, 'little')
        frame_be = int.from_bytes(data, 'big')
        return cls(
            node_id=(frame_le >> 0) & 0xFF,
            mode=(frame_le >> 8) & 0xFF,
            status=(frame_le >> 16) & 0xFF,
            arm_rx=(frame_le >> 24) & 0xFF,
            frames_sent=(frame_le >> 32) & 0xFFFF,
            frames_lost=(frame_le >> 48) & 0xFFFF,
        )

@dataclass
class Heartbeat:
    """État périodique d'un nœud (période par défaut 500 ms, configurable), suspendu pendant un test d'arbitrage. TEC et REC proviennent des registres du contrôleur (FDCAN ECR, bxCAN ESR) : aucun compteur d'erreur n'est réimplémenté en logiciel."""

    DLC = 8

    ctrl_state: int = 0.0
    last_error_code: int = 0.0
    clock_not_qualified: int = 0.0
    fault_mode_active: int = 0.0
    silent_mode: int = 0.0
    tec: int = 0.0
    rec: int = 0.0
    current_mode: int = 0.0
    reserved: int = 0.0
    rx_fifo_lost: int = 0.0
    ring_overflow: int = 0.0
    non_classic_rx: int = 0.0
    ext_id_rx: int = 0.0

    def pack(self) -> bytes:
        frame_le = 0
        frame_be = 0
        raw = _clamp(int(self.ctrl_state), 0, 3)
        frame_le |= (raw & 0x3) << 0
        raw = _clamp(int(self.last_error_code), 0, 7)
        frame_le |= (raw & 0x7) << 2
        raw = _clamp(int(self.clock_not_qualified), 0, 1)
        frame_le |= (raw & 0x1) << 5
        raw = _clamp(int(self.fault_mode_active), 0, 1)
        frame_le |= (raw & 0x1) << 6
        raw = _clamp(int(self.silent_mode), 0, 1)
        frame_le |= (raw & 0x1) << 7
        raw = _clamp(int(self.tec), 0, 255)
        frame_le |= (raw & 0xFF) << 8
        raw = _clamp(int(self.rec), 0, 255)
        frame_le |= (raw & 0xFF) << 16
        raw = _clamp(int(self.current_mode), 0, 15)
        frame_le |= (raw & 0xF) << 24
        raw = _clamp(int(self.reserved), 0, 15)
        frame_le |= (raw & 0xF) << 28
        raw = _clamp(int(self.rx_fifo_lost), 0, 255)
        frame_le |= (raw & 0xFF) << 32
        raw = _clamp(int(self.ring_overflow), 0, 255)
        frame_le |= (raw & 0xFF) << 40
        raw = _clamp(int(self.non_classic_rx), 0, 255)
        frame_le |= (raw & 0xFF) << 48
        raw = _clamp(int(self.ext_id_rx), 0, 255)
        frame_le |= (raw & 0xFF) << 56
        data = bytearray(frame_le.to_bytes(8, 'little'))
        if frame_be:
            be = frame_be.to_bytes(8, 'big')
            data = bytearray(a | b for a, b in zip(data, be))
        return bytes(data)

    @classmethod
    def unpack(cls, data: bytes):
        if len(data) != 8:
            raise ValueError(f'HEARTBEAT_N1 : {len(data)} octets reçus, 8 attendus')
        frame_le = int.from_bytes(data, 'little')
        frame_be = int.from_bytes(data, 'big')
        return cls(
            ctrl_state=(frame_le >> 0) & 0x3,
            last_error_code=(frame_le >> 2) & 0x7,
            clock_not_qualified=(frame_le >> 5) & 0x1,
            fault_mode_active=(frame_le >> 6) & 0x1,
            silent_mode=(frame_le >> 7) & 0x1,
            tec=(frame_le >> 8) & 0xFF,
            rec=(frame_le >> 16) & 0xFF,
            current_mode=(frame_le >> 24) & 0xF,
            reserved=(frame_le >> 28) & 0xF,
            rx_fifo_lost=(frame_le >> 32) & 0xFF,
            ring_overflow=(frame_le >> 40) & 0xFF,
            non_classic_rx=(frame_le >> 48) & 0xFF,
            ext_id_rx=(frame_le >> 56) & 0xFF,
        )

@dataclass
class EnergyCommand:
    """Commande énergie émise périodiquement par N1 ; contendant de rang 1 attendu."""

    DLC = 8

    torque_setpoint: float = 0.0
    speed_setpoint: float = 0.0
    current_limit: float = 0.0
    enable: int = 0.0
    direction: int = 0.0
    command_counter: int = 0.0
    checksum: int = 0.0

    def pack(self) -> bytes:
        frame_le = 0
        frame_be = 0
        raw = _clamp(bench_round((float(self.torque_setpoint) - (0.0)) / (0.1)), -32768, 32767)
        frame_le |= (raw & 0xFFFF) << 0
        raw = _clamp(bench_round((float(self.speed_setpoint) - (0.0)) / (0.5)), -32768, 32767)
        frame_le |= (raw & 0xFFFF) << 16
        raw = _clamp(bench_round((float(self.current_limit) - (0.0)) / (0.05)), 0, 4095)
        frame_le |= (raw & 0xFFF) << 32
        raw = _clamp(int(self.enable), 0, 1)
        frame_le |= (raw & 0x1) << 44
        raw = _clamp(int(self.direction), 0, 1)
        frame_le |= (raw & 0x1) << 45
        raw = _clamp(int(self.command_counter), 0, 255)
        frame_le |= (raw & 0xFF) << 48
        raw = _clamp(int(self.checksum), 0, 255)
        frame_le |= (raw & 0xFF) << 56
        data = bytearray(frame_le.to_bytes(8, 'little'))
        if frame_be:
            be = frame_be.to_bytes(8, 'big')
            data = bytearray(a | b for a, b in zip(data, be))
        return bytes(data)

    @classmethod
    def unpack(cls, data: bytes):
        if len(data) != 8:
            raise ValueError(f'ENERGY_COMMAND : {len(data)} octets reçus, 8 attendus')
        frame_le = int.from_bytes(data, 'little')
        frame_be = int.from_bytes(data, 'big')
        return cls(
            torque_setpoint=(_sign_extend((frame_le >> 0) & 0xFFFF, 16)) * 0.1 + 0.0,
            speed_setpoint=(_sign_extend((frame_le >> 16) & 0xFFFF, 16)) * 0.5 + 0.0,
            current_limit=((frame_le >> 32) & 0xFFF) * 0.05 + 0.0,
            enable=(frame_le >> 44) & 0x1,
            direction=(frame_le >> 45) & 0x1,
            command_counter=(frame_le >> 48) & 0xFF,
            checksum=(frame_le >> 56) & 0xFF,
        )

@dataclass
class ImuSpeed:
    """IMU et vitesse roue émises par N2 ; contendant de rang 2 attendu. Le capteur MPU-6050 (0x68) est utilisé s'il est détecté, sinon la séquence déterministe déclarée en bas de ce fichier prend le relais."""

    DLC = 8

    accel_x: float = 0.0
    accel_y: float = 0.0
    gyro_z: float = 0.0
    wheel_speed: float = 0.0
    sensor_present: int = 0.0
    frame_counter: int = 0.0

    def pack(self) -> bytes:
        frame_le = 0
        frame_be = 0
        raw = _clamp(bench_round((float(self.accel_x) - (0.0)) / (0.001)), -32768, 32767)
        frame_le |= (raw & 0xFFFF) << 0
        raw = _clamp(bench_round((float(self.accel_y) - (0.0)) / (0.001)), -32768, 32767)
        frame_le |= (raw & 0xFFFF) << 16
        raw = _clamp(bench_round((float(self.gyro_z) - (0.0)) / (0.0625)), -32768, 32767)
        frame_le |= (raw & 0xFFFF) << 32
        raw = _clamp(bench_round((float(self.wheel_speed) - (0.0)) / (0.25)), 0, 4095)
        frame_le |= (raw & 0xFFF) << 48
        raw = _clamp(int(self.sensor_present), 0, 1)
        frame_le |= (raw & 0x1) << 60
        raw = _clamp(int(self.frame_counter), 0, 7)
        frame_le |= (raw & 0x7) << 61
        data = bytearray(frame_le.to_bytes(8, 'little'))
        if frame_be:
            be = frame_be.to_bytes(8, 'big')
            data = bytearray(a | b for a, b in zip(data, be))
        return bytes(data)

    @classmethod
    def unpack(cls, data: bytes):
        if len(data) != 8:
            raise ValueError(f'IMU_SPEED : {len(data)} octets reçus, 8 attendus')
        frame_le = int.from_bytes(data, 'little')
        frame_be = int.from_bytes(data, 'big')
        return cls(
            accel_x=(_sign_extend((frame_le >> 0) & 0xFFFF, 16)) * 0.001 + 0.0,
            accel_y=(_sign_extend((frame_le >> 16) & 0xFFFF, 16)) * 0.001 + 0.0,
            gyro_z=(_sign_extend((frame_le >> 32) & 0xFFFF, 16)) * 0.0625 + 0.0,
            wheel_speed=((frame_le >> 48) & 0xFFF) * 0.25 + 0.0,
            sensor_present=(frame_le >> 60) & 0x1,
            frame_counter=(frame_le >> 61) & 0x7,
        )

@dataclass
class TempBattery:
    """Température et état batterie émis par N3 ; contendant de rang 3 attendu. Le DS18B20 est utilisé s'il est détecté, sinon la séquence déterministe."""

    DLC = 8

    temperature: float = 20.0
    pack_voltage: float = 0.0
    pack_current: float = 0.0
    state_of_charge: int = 0.0
    sensor_present: int = 0.0
    frame_counter: int = 0.0

    def pack(self) -> bytes:
        frame_le = 0
        frame_be = 0
        raw = _clamp(bench_round((float(self.temperature) - (0.0)) / (0.0625)), -32768, 32767)
        frame_le |= (raw & 0xFFFF) << 0
        raw = _clamp(bench_round((float(self.pack_voltage) - (0.0)) / (0.01)), 0, 65535)
        frame_le |= (raw & 0xFFFF) << 16
        raw = _clamp(bench_round((float(self.pack_current) - (0.0)) / (0.01)), -32768, 32767)
        frame_le |= (raw & 0xFFFF) << 32
        raw = _clamp(int(self.state_of_charge), 0, 127)
        frame_le |= (raw & 0x7F) << 48
        raw = _clamp(int(self.sensor_present), 0, 1)
        frame_le |= (raw & 0x1) << 55
        raw = _clamp(int(self.frame_counter), 0, 255)
        frame_le |= (raw & 0xFF) << 56
        data = bytearray(frame_le.to_bytes(8, 'little'))
        if frame_be:
            be = frame_be.to_bytes(8, 'big')
            data = bytearray(a | b for a, b in zip(data, be))
        return bytes(data)

    @classmethod
    def unpack(cls, data: bytes):
        if len(data) != 8:
            raise ValueError(f'TEMP_BATTERY : {len(data)} octets reçus, 8 attendus')
        frame_le = int.from_bytes(data, 'little')
        frame_be = int.from_bytes(data, 'big')
        return cls(
            temperature=(_sign_extend((frame_le >> 0) & 0xFFFF, 16)) * 0.0625 + 0.0,
            pack_voltage=((frame_le >> 16) & 0xFFFF) * 0.01 + 0.0,
            pack_current=(_sign_extend((frame_le >> 32) & 0xFFFF, 16)) * 0.01 + 0.0,
            state_of_charge=(frame_le >> 48) & 0x7F,
            sensor_present=(frame_le >> 55) & 0x1,
            frame_counter=(frame_le >> 56) & 0xFF,
        )


#: Classe de décodage associée à chaque disposition de trame.
LAYOUTS = {
    'BENCH_CFG': BenchCfg,
    'BENCH_RESULT': BenchResult,
    'ENERGY_COMMAND': EnergyCommand,
    'HEARTBEAT': Heartbeat,
    'IMU_SPEED': ImuSpeed,
    'TEMP_BATTERY': TempBattery,
}
