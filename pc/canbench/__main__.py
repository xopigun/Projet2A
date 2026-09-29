"""Permet ``python -m canbench``, sans installation du paquet."""

from .cli import main

raise SystemExit(main())
