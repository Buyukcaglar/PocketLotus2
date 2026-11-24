# M8 announcement drafts

Drafts for the M8 posts in [ROADMAP.md](ROADMAP.md). Nothing here has been posted. Every post links the README's game content section and names what is untested.

Links used below:

- Repository: https://github.com/Buyukcaglar/PocketLotus2
- Game content: https://github.com/Buyukcaglar/PocketLotus2#game-content
- Building: https://github.com/Buyukcaglar/PocketLotus2#building
- How it works: https://github.com/Buyukcaglar/PocketLotus2/blob/main/docs/PORT_ARCHITECTURE.md

Untested, named in every post: link-cable play on two real Pockets (tested between two desktop instances), the second-disk courses, and two controllers on a Dock.

## 1. openFPGA core list: question before listing

Where: new issue (blank, not the New Core form) on https://github.com/openfpga-library/analogue-pocket

Title: How should a build-it-yourself core be listed?

Posted 24 November 2026 as [openfpga-library/analogue-pocket#2055](https://github.com/openfpga-library/analogue-pocket/issues/2055). Wait for the answer before using the New Core form.

> I have released PocketLotus2, the Acorn Archimedes version of Lotus Turbo Challenge 2 statically recompiled for openfpgaOS on the Pocket: https://github.com/Buyukcaglar/PocketLotus2
>
> The core cannot be offered as a download, because a built core contains translated game code and data. Users build it from their own disks with one command (https://github.com/Buyukcaglar/PocketLotus2#building, game content policy: https://github.com/Buyukcaglar/PocketLotus2#game-content).
>
> The GitHub release has one asset, a zip of the core files that contain no game (the openfpgaOS bitstream and loader, core and platform definitions, platform art). It is not a working core on its own. If the list pointed updaters such as pupdate or Pocket Sync at it, they would install a core that cannot start the game.
>
> Is there a way to list a core as "build from source" without a download, or would you prefer it is left off the list and linked elsewhere? I am happy to rename or move the release asset if that helps the updaters skip it.

## 2. openfpgaOS developers

Where: new issue on https://github.com/openfpgaOS/openfpgaSDK (Discussions are not enabled)

Title: PocketLotus2: Lotus Turbo Challenge 2 (Archimedes) as a static recompilation on openfpgaOS

Posted 24 November 2026 as [openfpgaOS/openfpgaSDK#9](https://github.com/openfpgaOS/openfpgaSDK/issues/9).

> Thank you for openfpgaOS and the SDK. I wanted to let you know about a port built on it: https://github.com/Buyukcaglar/PocketLotus2
>
> The Archimedes ARM2 program is translated to C and compiled for the Pocket's RISC-V processor, with a small runtime for the RISC OS calls and hardware the game uses. The translated code matches an ARM interpreter frame for frame over 40,000 frames. It runs at the game's 50 Hz (about 1.4 M of the 2 M cycles per race frame in the SDK simulator), with music and sound, saves to slot 0, and has two-Pocket play over the link cable in lockstep.
>
> Notes that may be useful to you: the SDK desktop shim flips at 60 Hz, so the core paces itself with a 20 ms clock unless the display really runs at 50 Hz; the platform ID must be lowercase; and the Pocket shows the framebuffer 2 pixels right of where it is written. Details are in https://github.com/Buyukcaglar/PocketLotus2/blob/main/docs/PORT_ARCHITECTURE.md.
>
> No game content is distributed; users build the core from their own disks (https://github.com/Buyukcaglar/PocketLotus2#game-content). Untested so far: link play on two real Pockets, the second-disk courses and two controllers on a Dock. Feel free to close this if issues are not the place for it.

## 3. FPGA Gaming Discord

Where: the Pocket or openFPGA development channel.

> PocketLotus2: Lotus Turbo Challenge 2 (Acorn Archimedes, 1992) on the Analogue Pocket, as a static recompilation on openfpgaOS. Full first-disk game at 50 Hz with music, names and password with the d-pad, saves, and two-Pocket play over the link cable (each player full screen), which the original never had.
> You build it from your own disks with one command; no game content is included: https://github.com/Buyukcaglar/PocketLotus2#game-content
> Untested so far: link play on two real Pockets, the disk 2 courses and two controllers on a Dock. Reports welcome.

## 4. Reddit r/AnaloguePocket

Title: PocketLotus2: Lotus Turbo Challenge 2 (Archimedes) on the Pocket via openfpgaOS, with two-Pocket link play

Posted 24 November 2026 on r/AnaloguePocket.

> I have ported the Acorn Archimedes version of Lotus Turbo Challenge 2 to the Pocket. It is a static recompilation: the original ARM program is translated to C and runs on openfpgaOS, matching the original frame for frame.
>
> - The complete first-disk game at the original 50 Hz, with music and sound
> - Two players on one docked Pocket with the game's split screen
> - Two players on two Pockets over the link cable, each with its own car full screen
> - Names and password with the d-pad; high scores and options saved
>
> There is no download: the core contains the game, so you build it from your own disks. On Windows that is a double-click and about a minute. See https://github.com/Buyukcaglar/PocketLotus2#building and https://github.com/Buyukcaglar/PocketLotus2#game-content.
>
> Not yet tested: link play on two real Pockets, the second-disk courses and two controllers on a Dock. If you try any of them, please tell me how it went.

Attach: short race video, and link play once it has been tried on two Pockets.

## 5. News tips

Where: contact forms or tip addresses of Time Extension, RetroRGB and Retro Game Corps.

Subject: New Analogue Pocket core: Lotus Turbo Challenge 2 (Acorn Archimedes) on openfpgaOS

> PocketLotus2 brings the 1992 Acorn Archimedes version of Lotus Turbo Challenge 2 to the Analogue Pocket as a static recompilation on openfpgaOS: https://github.com/Buyukcaglar/PocketLotus2
>
> It runs the complete first-disk game at the original 50 Hz with music and sound, saves high scores and options, and adds two-player play over the link cable between two Pockets, which the Archimedes version never had.
>
> No game content is distributed; players build the core from their own disks with a one-step builder (https://github.com/Buyukcaglar/PocketLotus2#game-content). Link play on two real Pockets and the second-disk courses are not yet tested.

## 6. Acorn communities

Where: StarDot (Archimedes games section), RISC OS Open forums (general or off-topic), r/acorn.

Title: Lotus Turbo Challenge 2 recompiled from ARM2 for the Analogue Pocket

> I have statically recompiled the Archimedes version of Lotus Turbo Challenge 2 to run on the Analogue Pocket under openfpgaOS: https://github.com/Buyukcaglar/PocketLotus2
>
> Some details Acorn people may enjoy: the X Lock loader is decrypted statically, so the protected sector is not needed; the game's OS calls are handled by a small RISC OS layer (it reads keys with OS_Byte 121, and the music module turned out to use only the sound system interface, so it is recompiled along with the game); raster palette changes are timed per scanline as on VIDC; and the black strip at the left of the race view is the game's own scroll-seam mask. The write-up is at https://github.com/Buyukcaglar/PocketLotus2/blob/main/docs/PORT_ARCHITECTURE.md.
>
> Nothing from the game is distributed; you build the core from your own disks or the JASPP package (https://github.com/Buyukcaglar/PocketLotus2#game-content). The second-disk courses and link play on two real Pockets are not yet tested.

## 7. Technical audiences

Show HN title: Show HN: Lotus Turbo Challenge 2 recompiled from ARM2 to RISC-V for the Analogue Pocket

Link: https://github.com/Buyukcaglar/PocketLotus2/blob/main/docs/PORT_ARCHITECTURE.md

First comment:

> Author here. This is a static recompilation of a 1992 Acorn Archimedes game: the ARM2 code (with PSR-in-R15, conditional execution and a self-modifying word) is translated to C, built for the RISC-V soft CPU of openfpgaOS on the Analogue Pocket, and checked against an ARM interpreter, which matches frame for frame and sample for sample over 40,000 frames. Two Pockets play over the link cable in lockstep by exchanging only pad input. The game itself is not included; the core is built from the user's disks (https://github.com/Buyukcaglar/PocketLotus2#game-content). Untested so far: link play on two real Pockets and the second-disk courses.

Also send the write-up link to static-recompilation projects and lists (for example N64Recomp and XenonRecomp communities).
