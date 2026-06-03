from dataclasses import dataclass


@dataclass(frozen=True)
class EpochSeed:
    value: int

    @property
    def chaos_seed(self) -> int:
        return self.value ^ 0xA1B2C3D4

    @property
    def jitter_seed(self) -> int:
        return self.value ^ 0xE5F6A7B8

    @property
    def migration_seed(self) -> int:
        return self.value ^ 0xC9D0E1F2

    @property
    def replay_seed(self) -> int:
        return self.value ^ 0x3A4B5C6D

    @property
    def perturbation_seed(self) -> int:
        return self.value ^ 0x7E8F9A0B
