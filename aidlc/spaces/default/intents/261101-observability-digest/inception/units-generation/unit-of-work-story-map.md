# Requirement Map

Sources: `inception/requirements-analysis/requirements.md` (no user stories were produced, so rows are keyed
by FR) and `unit-of-work.md`.

| ID | Unit ID | Directory |
|----|---------|-----------|
| FR1.1 | U3; U5 | u3-health-dashboard; u5-warnings-and-errors |
| FR1.2 | U3; U5 | u3-health-dashboard; u5-warnings-and-errors |
| FR1.3 | U3 | u3-health-dashboard |
| FR1.4 | U5 | u5-warnings-and-errors |
| FR1.5 | U3 | u3-health-dashboard |
| FR1.6 | U3; U5 | u3-health-dashboard; u5-warnings-and-errors |
| FR1.7 | U3; U5 | u3-health-dashboard; u5-warnings-and-errors |
| FR1.8 | U3 | u3-health-dashboard |
| FR2.1 | U2; U5 | u2-log-events; u5-warnings-and-errors |
| FR2.2 | U2; U5 | u2-log-events; u5-warnings-and-errors |
| FR2.3 | U2 | u2-log-events |
| FR2.4 | U2 | u2-log-events |
| FR3.1 | U5 | u5-warnings-and-errors |
| FR3.2 | U5 | u5-warnings-and-errors |
| FR4.1 | U5 | u5-warnings-and-errors |
| FR4.2 | U4 | u4-sturdy-alarms |
| FR5.1 | U4 | u4-sturdy-alarms |
| FR5.2 | U2; U4 | u2-log-events; u4-sturdy-alarms |
| FR5.3 | U4 | u4-sturdy-alarms |
| FR5.4 | U5 | u5-warnings-and-errors |
| FR6.1 | U1 | u1-logging-review |
| FR6.2 | U1 | u1-logging-review |
| FR6.3 | U2 | u2-log-events |
| NFR1 | U3; U5 | u3-health-dashboard; u5-warnings-and-errors |
| NFR2 | U3 | u3-health-dashboard |
| NFR3 | U3; U5 | u3-health-dashboard; u5-warnings-and-errors |

## Cross-Cutting Rows

- FR1.1, FR1.2, FR1.6, FR1.7: U3 builds the dashboard and verdict; U5 adds the error-log alarm to the verdict, the totals, and the errors-and-warnings area with its phone and empty states.
- FR2.1, FR2.2: U2 makes every warning and error carry its kind; U5 counts and shows them.
- FR5.2: U2 has the Python half of the drift test, U4 the Terraform half.
- NFR4 to NFR6 (offline tests, no regressions, pipeline delivery) apply to every unit.

## What Each Unit Contains

The order of work inside a unit is chosen later; these lists are unordered.

- U1: an inventory of every log call; event-name decisions; level and field decisions; any new warnings; the secrets check.
- U2: the formatter move; event names on every warning, error and the message-sent line; the tidy-up U1 decides; the Python test.
- U3: the two composite alarms; the dashboard's verdict, signal tiles and detail widgets.
- U4: the moved signal filters; the Terraform test.
- U5: the warning and error-log filters and alarms; the error-log alarm in the verdict; the errors-and-warnings area and the totals.

## Coverage Verification

Every FR sub-requirement (FR1.1 to FR6.3) is assigned to at least one unit, and every unit U1 to U5 has rows.
