// All amounts are integer atomic units (12 decimals in FEEL).
// This determines an upper bound, NOT funds automatically owned by the faucet.
export function budgetAtomic({emitted, fractionNumerator=5n, fractionDenominator=1000n, cap, funded}) {
  for (const amount of [emitted, fractionNumerator, fractionDenominator, cap, funded]) {
    if (typeof amount !== "bigint" || amount < 0n) throw new TypeError("Amounts must be non-negative bigint values");
  }
  if (!fractionDenominator || fractionNumerator > fractionDenominator) throw new RangeError("Invalid budget fraction");
  const emissionAllowance = emitted * fractionNumerator / fractionDenominator;
  return [emissionAllowance, cap, funded].reduce((a,b) => a < b ? a : b);
}
export function formatFeel(atomic) {
  if (typeof atomic !== "bigint" || atomic < 0n) throw new TypeError("Invalid amount");
  const whole = atomic / 1000000000000n;
  const fraction = (atomic % 1000000000000n).toString().padStart(12,"0").replace(/0+$/,"");
  return whole.toString() + (fraction ? "." + fraction : "");
}
