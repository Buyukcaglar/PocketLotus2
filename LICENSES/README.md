# Source notices

New PocketLotus RTL, diagnostic, tests and tools are licensed under
GPL-3.0-or-later. SPDX identifiers identify these files. Imported source retains
its complete original notices and SHA-256 provenance in `source-manifest.json`.

Amber ARM26 RTL is LGPL-2.1-or-later. The two `sram_*_en.v` wrappers have no
per-file license header in the pinned tree; their Amber provenance is recorded,
and distribution needs review rather than an invented upstream notice.
MEMC, VIDC, IOC and latches carry
Stephen J. Leary's BSD-style three-clause notices (including the original
organization placeholder). These notices remain verbatim in every file.

Pocket APF source and command handler are from the pinned PocketRiscV tree.
APF carries the Analogue Software License Agreement and refers to
https://www.analogue.link/pocket-eula. Intel-generated megafunction source
carries its separate tool/IP agreement. The reference QSF is retained as an
unaltered pin/IO-settings source, not an active project. README license
summaries do not override file notices.

The integration is independently wired from the chipset interfaces; the GPL
Archimedes top is a reference, not an imported module. FDC and IDE are omitted
from the diagnostic target. The RiscDev IDE ROM, user RISC OS ROM, ADFFS and
Lotus content are separate future dependencies and are excluded.

Full GPL and LGPL texts are included here. No game/ROM redistribution is
authorized by this source manifest.
