export class ContractError extends Error {
  constructor(readonly specId: string, readonly phase: "requires" | "ensures") {
    super(`${specId}: contract violation (${phase})`);
    this.name = "ContractError";
  }
}

// Deliberately synchronous. For this pilot, conditions inspect immutable inputs.
export function contract<Args extends unknown[], Result>(
  specId: string,
  run: (...args: Args) => Result,
  conditions: {
    requires: (...args: Args) => boolean;
    ensures: (result: Result, ...args: Args) => boolean;
  },
): (...args: Args) => Result {
  return (...args) => {
    if (!conditions.requires(...args)) throw new ContractError(specId, "requires");
    const result = run(...args);
    if (!conditions.ensures(result, ...args)) throw new ContractError(specId, "ensures");
    return result;
  };
}
