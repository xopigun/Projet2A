/**
 * @file interrupts.c
 * @brief Gestionnaires d'interruption système, communs aux deux cartes.
 *
 * Le fichier de démarrage de ST déclare chaque vecteur comme un alias faible de
 * `Default_Handler`, qui boucle indéfiniment. Tout vecteur activé doit donc être
 * redéfini ici ou dans un port, faute de quoi le cœur s'y bloque sans rien dire.
 *
 * C'est arrivé : sans `SysTick_Handler`, la première interruption de base de
 * temps, une milliseconde après `HAL_Init()`, figeait le nœud avant même le
 * premier message. `scripts/check_vectors.py`, lancé après chaque édition de
 * liens, vérifie désormais qu'aucun vecteur utilisé ne retombe sur
 * `Default_Handler`.
 */

#include "board.h"

/** Base de temps de la HAL : HAL_GetTick() et tous les délais en dépendent. */
void SysTick_Handler(void) {
    HAL_IncTick();
}
