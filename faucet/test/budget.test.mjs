import test from "node:test";
import assert from "node:assert/strict";
import {budgetAtomic,formatFeel} from "../lib/budget.mjs";

test("daily allowance cannot exceed emission ratio, cap or funded balance",()=>{
  assert.equal(budgetAtomic({emitted:1000000n,cap:4000n,funded:9000n}),4000n);
  assert.equal(budgetAtomic({emitted:1000000n,cap:9000n,funded:2000n}),2000n);
  assert.equal(budgetAtomic({emitted:1000000n,cap:9000n,funded:9000n}),5000n);
  assert.equal(budgetAtomic({emitted:0n,cap:9000n,funded:9000n}),0n);
});
test("money math remains integer-safe and fails closed",()=>{
  assert.equal(formatFeel(1250000000000n),"1.25");
  assert.equal(formatFeel(1n),"0.000000000001");
  assert.throws(()=>budgetAtomic({emitted:-1n,cap:10n,funded:10n}));
  assert.throws(()=>budgetAtomic({emitted:100n,cap:100n,funded:100n,fractionDenominator:0n}));
});
