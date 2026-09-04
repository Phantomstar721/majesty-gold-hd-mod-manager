# Stock GPLMx Purchase_Equipment tail callbacks

`stock.gplmx-purchase-equipment-tail.v1` is a source-composed callback point,
not a native hook. Stock expansion heroes call `Purchase_Equipment`; its final
choice is `Stat_Boost_Check`. If every choice declines, the function returns
FALSE. If any choice succeeds, the one stock final block sets
`ActiveScript = Use_Building` and returns TRUE.

The manager preserves that lifecycle literally. It begins with the complete
effective merged function when a selected mod already extends it, otherwise
with the installed SDK's stock GPLMx source. It proves the ordered stock checks
and exact final handoff, then inserts each package-declared boolean callback
between `Stat_Boost_Check` and the final handoff. Each callback runs only while
`Flag` is FALSE. The stable order is normalized mod UUID, package-local
callback key, then symbol, so selection order cannot change behavior.

Callbacks own only their package's decision and preparation: they return TRUE
after assigning the Target/TaskName/intent state required by the stock visit
lifecycle. The manager neither polls nor launches a parallel script. Missing
functions, wrong signatures, duplicate symbols, altered stock anchors, and
unresolved GPL conflicts fail closed before compilation.

`stock.gplmx-purchase-bazaar-tail.v1` applies the same guarded composition to
`Purchase_Bazaar`. It proves the stock six-item scan and inserts callbacks only
after that scan has selected no Bazaar purchase, before the same final
Flag/`Use_Building` handoff. This later extension point is appropriate when a
custom visit must not preempt Magic Bazaar shopping.
