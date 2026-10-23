# LT2 v3 feature additions

The additions use the existing eight LT2 pages, theme, controls, notifications,
selection highlights, and job/Stop handling. The main hub GUI is unchanged.
Reload the hub and choose Lumber Tycoon 2 to load the updated module.

| Existing page | Added feature | Behavior |
| --- | --- | --- |
| Tools | Lasso Selection | Drag a rectangle to add visible centers of owned objects/logs. It excludes other players' objects and shares the normal selection list. |
| Tools | Pyramid Sorter | Enable under Selection Settings, then use the existing Sort button. X/Z define the base and Y caps layers. Layout capacity is checked before moving anything. |
| Tools | Match Plank Length In Groups | Group selection matches wood class and, when enabled, length within 0.05 studs. |
| Tools | Select All My Planks / Loose Items | Adds owned planks or unanchored owned items; blueprint models are excluded from loose-item selection. |
| Plot | Blueprint Filling | Scan owned planks, choose a wood class or click a sample plank, and set minimum/maximum length. Length sliders show tenths of a stud. |
| Plot | Click To Fill Blueprint | Clicking an owned blueprint delivers a matching owned plank and checks for consumption/completion. |
| Plot | Fill All My Blueprints | Visits owned blueprints, delivers matching planks, and stops a stalled blueprint when consumption is not confirmed. |
| Shop | Blueprint Purchases | Uses the reference's 69 blueprint IDs, checks unlocked inventory and current scanned stock, verifies funds, buys and opens boxes, and waits for unlock confirmation. Already owned entries are skipped. |
| Shop | Rukiryaxe Quest | Reuses owned materials or buys/opens worms, sand, and a light bulb, delivers them to the reference's shrine positions, waits for a new nearby reward, and verifies pickup in inventory. |

## Lifecycle and validation

New click tools are mutually exclusive. Stop cancels active new jobs and click
modes. Ownership loops check the job token. Purchase/fill/quest jobs restore the
starting position after completion, failure, or cancellation, but do not teleport
the player out of a newer job. Unload removes added selection overlays and
stops background work through the existing lifecycle.

The store purchase predicate was corrected to verify the actual owner of the
purchased model; merely being in PlayerModels is no longer treated as success.
Cashier invocation failures now propagate instead of being treated as successful
just because the call returned.

The regression suite runs the actual module initialization and added callbacks
with simulated Roblox objects, remotes, input signals, purchases, plank
consumption, and quest rewards:

```sh
python -m pip install lupa
python tests/test_lt2_features.py
```

It covers the existing eight pages, inactive startup controls, ownership and
length filters, layout bounds, lasso input, fill progress and stalling, purchases,
quest sequencing, cancellation, and return-position isolation.

**Not live-tested inside LT2.** The game may change item schemas, remotes,
shop availability, shrine coordinates, or server ownership behavior. Runtime
checks and bounded waits report missing prerequisites or unconfirmed outcomes;
the tests do not establish that a real server will accept an operation. Blueprint
filling requires suitable planks and the game's normal material requirements.

## Reference scope

The uploaded source contains its own complete GUI, branding, reload URL,
startup file handling, a cross-server bootstrap, duplication modules, advanced
cutters, and a large wire/blueprint file builder. Those systems were not imported.
The adapted portions are the selection/layout mechanics, blueprint material
workflow, blueprint catalog/purchase flow, and Rukiryaxe recipe. No new HTTP
requests, external script execution, filesystem deletion, or startup persistence
were added to Lt2.txt. The original upload was not executed.
