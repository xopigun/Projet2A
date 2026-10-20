/**
 * @file syscalls.c
 * @brief Appels système minimaux pour la newlib, sur cible sans système.
 *
 * `--specs=nosys.specs` fournirait ces symboles, mais au prix d'un
 * avertissement d'édition de liens par appel non implémenté. Le projet compile
 * sans avertissement : on fournit donc nos propres talons, qui échouent
 * proprement plutôt que bruyamment.
 *
 * `_write` est branché sur le journal série lorsqu'il est actif — port COM
 * virtuel du ST-LINK sur la Nucleo, USART1 sur la Blue Pill — ce qui rend
 * `printf()` utilisable pour le diagnostic sans rien changer d'autre.
 */

#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include "board.h"

/** Renseigné par le firmware si le journal série est ouvert. */
UART_HandleTypeDef *bench_log_uart;

extern char end;  /* fin des données statiques, fournie par le script d'édition */

void *_sbrk(ptrdiff_t increment) {
    static char *heap = &end;
    char *previous = heap;

    /* La pile descend depuis le haut de la RAM : on refuse de la rejoindre. */
    char *const limit = (char *)__get_MSP();
    if (heap + increment > limit) {
        errno = ENOMEM;
        return (void *)-1;
    }

    heap += increment;
    return previous;
}

int _write(int file, char *buffer, int length) {
    if (file != STDOUT_FILENO && file != STDERR_FILENO) {
        errno = EBADF;
        return -1;
    }
#if BENCH_HAS_SERIAL_LOG
    if (bench_log_uart != NULL && length > 0) {
        (void)HAL_UART_Transmit(bench_log_uart, (uint8_t *)buffer, (uint16_t)length, 100u);
    }
#else
    (void)buffer;
#endif
    return length;
}

int _read(int file, char *buffer, int length) {
    (void)file;
    (void)buffer;
    (void)length;
    return 0;  /* fin de fichier : aucune entrée sur la cible */
}

int _close(int file) {
    (void)file;
    return -1;
}

int _fstat(int file, struct stat *status) {
    (void)file;
    status->st_mode = S_IFCHR;
    return 0;
}

int _isatty(int file) {
    (void)file;
    return 1;
}

off_t _lseek(int file, off_t offset, int whence) {
    (void)file;
    (void)offset;
    (void)whence;
    return 0;
}

int _getpid(void) {
    return 1;
}

int _kill(int pid, int signal) {
    (void)pid;
    (void)signal;
    errno = EINVAL;
    return -1;
}

void _exit(int status) {
    (void)status;
    __disable_irq();
    for (;;) {
    }
}
