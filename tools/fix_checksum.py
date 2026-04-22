#!/usr/bin/env python3
from pathlib import Path
import sys


def fix_checksum(path: Path) -> None:
    data = bytearray(path.read_bytes())

    # LoROM header checksum fields in bank 00:
    # complement: 0x7FDC-0x7FDD, checksum: 0x7FDE-0x7FDF
    comp_off = 0x7FDC
    sum_off = 0x7FDE

    # Canonical pre-sum state per SNES header convention: complement starts
    # as $FFFF, checksum as $0000. This makes the final byte sum of the ROM
    # (mod $10000) equal to the stored checksum, which a few copier tools
    # verify after writing the cart.
    data[comp_off:comp_off + 2] = b"\xFF\xFF"
    data[sum_off:sum_off + 2] = b"\x00\x00"

    checksum = sum(data) & 0xFFFF
    complement = checksum ^ 0xFFFF

    data[comp_off] = complement & 0xFF
    data[comp_off + 1] = (complement >> 8) & 0xFF
    data[sum_off] = checksum & 0xFF
    data[sum_off + 1] = (checksum >> 8) & 0xFF

    path.write_bytes(data)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: fix_checksum.py <rom.sfc>")
        return 1
    fix_checksum(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
