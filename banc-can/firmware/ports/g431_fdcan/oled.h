/**
 * @file oled.h
 * @brief Écran OLED SSD1306 128 × 64 sur I2C1 (PA15 SCL, PB7 SDA), adresse 0x3C.
 *
 * L'image est envoyée page par page (128 octets) en I2C sur interruption : la
 * boucle principale n'attend jamais l'écran, ce qui préserve la cadence de 20 ms
 * des trames applicatives et la vidange du tampon CAN. Une image complète part
 * en une centaine de millisecondes à 100 kHz.
 *
 * Sans écran branché, bench_oled_init() renvoie false et toutes les autres
 * fonctions deviennent sans effet : le même firmware sert aux quatre nœuds.
 */

#ifndef BENCH_OLED_H
#define BENCH_OLED_H

#include <stdbool.h>
#include <stdint.h>

/** @brief Configure I2C1, cherche l'écran et l'initialise. @return true s'il répond. */
bool bench_oled_init(void);

/** @brief Vrai si l'écran a répondu à l'initialisation. */
bool bench_oled_present(void);

/** @brief Vrai si aucune image n'est en cours d'envoi : on peut en préparer une. */
bool bench_oled_idle(void);

/**
 * @brief Lance l'envoi de l'image @p fb (1024 octets), qui doit rester valable
 *        jusqu'à ce que bench_oled_idle() redevienne vrai.
 */
void bench_oled_show(const uint8_t *fb);

/** @brief Fait avancer l'envoi en cours ; à appeler à chaque tour de boucle. */
void bench_oled_poll(void);

#endif /* BENCH_OLED_H */
