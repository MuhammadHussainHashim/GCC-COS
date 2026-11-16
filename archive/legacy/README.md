# Archived prototype source — reference only

These three folders are an unchanged source-tree recovery from user-created
ZIP archives. They are **not** imported by `gcc_cos`, not tested as part of the
new production CLI, and may contain stale endpoints, weak validation or
inappropriate status labels. The core 0.5.0 pipeline is authoritative.

- `GCC_COS_Automation_System/`: earlier Streamlit CSV/Excel/Comtrade prototype.
- `COS_Carbon_Tool/`: earlier command-line spreadsheet importer/exporter.
- `COS_Carbon_Source_Collector/`: earlier multi-source download experiment.

The old `COS_Carbon_Tool` export code uses a broad list of status labels,
including an `Estimated` label, in a sheet named `Approved Status`. **Do not
interpret that legacy sheet as verified evidence.** No API keys are included
in the recovered source snapshot. Use the new evidence controls instead.
