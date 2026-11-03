/**
 * @file lcd.h
 * @brief Afficheur LCD 16x2 HD44780 en mode 4 bits, écriture seule.
 *
 * Compilé seulement si board.h définit BENCH_HAS_LCD ; brochage dans board.h,
 * câblage dans docs/latex/schema_ecrans_lcd.tex.
 *
 * Le rafraîchissement ne bloque jamais la boucle principale. bench_lcd_show()
 * ne fait que noter le texte voulu ; bench_lcd_service(), appelée à chaque tour
 * de boucle, envoie au plus un octet à l'écran, et seulement là où l'écran
 * diffère du texte voulu. Un tour coûte ainsi quelques microsecondes, quand un
 * rafraîchissement complet bloquant en coûterait près de 2 ms : de quoi décaler
 * la réponse de N2, calée 5 ms après la trame de N1, de façon visible à
 * l'oscilloscope.
 *
 * R/W étant à la masse, le drapeau « occupé » du contrôleur ne peut pas être lu :
 * chaque octet est suivi d'un délai fixe, plus long que son temps d'exécution.
 */

#ifndef BENCH_G431_LCD_H
#define BENCH_G431_LCD_H

#include "app/lcd_text.h"

/**
 * @brief Configure les broches et initialise le contrôleur ; écran effacé.
 *
 * Bloquante, environ 60 ms : à appeler une fois au démarrage, après
 * bench_clock_config(), avant l'ouverture du contrôleur CAN.
 */
void bench_lcd_init(void);

/** @brief Note le texte à afficher. Ne touche pas à l'écran ; voir bench_lcd_service(). */
void bench_lcd_show(const bench_lcd_text_t *text);

/** @brief Envoie au plus un octet vers l'écran. À appeler à chaque tour de boucle. */
void bench_lcd_service(void);

/** @brief Attend que l'écran montre tout le texte noté. Bloquante, 2 ms au plus. */
void bench_lcd_flush(void);

#endif /* BENCH_G431_LCD_H */
