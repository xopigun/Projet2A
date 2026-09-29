/*
 * Script d'édition de liens du STM32G431KBT6 (boîtier UFQFPN32).
 *
 * Cartographie mémoire (RM0440 Rev 9 §2.4, appareils de catégorie 2) : 128 Ko
 * de flash et 32 Ko de SRAM. SRAM1 (16 Ko) est à 0x20000000, SRAM2 (6 Ko) à
 * 0x20004000, et la CCM SRAM (10 Ko) est aliasée juste après, à 0x20005800 :
 * l'espace est contigu, d'où une seule région. La CCM reste aussi accessible
 * à 0x10000000.
 */

ENTRY(Reset_Handler)

/* La pile part du sommet de la RAM et descend. */
_estack = ORIGIN(RAM) + LENGTH(RAM);

_Min_Heap_Size  = 0x200;   /* 512 octets */
_Min_Stack_Size = 0x400;   /* 1 Kio */

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 128K
  RAM   (xrw) : ORIGIN = 0x20000000, LENGTH = 32K
}

SECTIONS
{
  /* Table des vecteurs, obligatoirement en tête de la flash. */
  .isr_vector :
  {
    . = ALIGN(4);
    KEEP(*(.isr_vector))
    . = ALIGN(4);
  } >FLASH

  .text :
  {
    . = ALIGN(4);
    *(.text)
    *(.text*)
    *(.glue_7)
    *(.glue_7t)
    *(.eh_frame)

    KEEP (*(.init))
    KEEP (*(.fini))

    . = ALIGN(4);
    _etext = .;
  } >FLASH

  .rodata :
  {
    . = ALIGN(4);
    *(.rodata)
    *(.rodata*)
    . = ALIGN(4);
  } >FLASH

  .ARM.extab : { *(.ARM.extab* .gnu.linkonce.armextab.*) } >FLASH
  .ARM : {
    __exidx_start = .;
    *(.ARM.exidx*)
    __exidx_end = .;
  } >FLASH

  .preinit_array :
  {
    PROVIDE_HIDDEN (__preinit_array_start = .);
    KEEP (*(.preinit_array*))
    PROVIDE_HIDDEN (__preinit_array_end = .);
  } >FLASH

  .init_array :
  {
    PROVIDE_HIDDEN (__init_array_start = .);
    KEEP (*(SORT(.init_array.*)))
    KEEP (*(.init_array*))
    PROVIDE_HIDDEN (__init_array_end = .);
  } >FLASH

  .fini_array :
  {
    PROVIDE_HIDDEN (__fini_array_start = .);
    KEEP (*(SORT(.fini_array.*)))
    KEEP (*(.fini_array*))
    PROVIDE_HIDDEN (__fini_array_end = .);
  } >FLASH

  /* Adresse en flash des données initialisées, lue par Reset_Handler. */
  _sidata = LOADADDR(.data);

  .data :
  {
    . = ALIGN(4);
    _sdata = .;
    *(.data)
    *(.data*)
    . = ALIGN(4);
    _edata = .;
  } >RAM AT> FLASH

  . = ALIGN(4);
  .bss :
  {
    _sbss = .;
    __bss_start__ = _sbss;
    *(.bss)
    *(.bss*)
    *(COMMON)
    . = ALIGN(4);
    _ebss = .;
    __bss_end__ = _ebss;
  } >RAM

  /* Vérifie qu'il reste assez de place pour le tas et la pile : mieux vaut une
   * erreur d'édition de liens qu'un débordement de pile en fonctionnement. */
  ._user_heap_stack :
  {
    . = ALIGN(8);
    PROVIDE ( end = . );
    PROVIDE ( _end = . );
    . = . + _Min_Heap_Size;
    . = . + _Min_Stack_Size;
    . = ALIGN(8);
  } >RAM

  /* Les modèles ST comportent ici un bloc /DISCARD/ écartant libc, libm et
   * libgcc. Il est volontairement absent : le code généré depuis l'ICD appelle
   * llround(), donc libm doit être conservée. */

  .ARM.attributes 0 : { *(.ARM.attributes) }
}
