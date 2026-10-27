"""Flow lab: test the viewer's experience of a weave, not just whether its buttons work.

walk    every route through the weave graph, plus the plain line under each room preference, with runtimes
seams   every distinct switch (A then B), 10 s either side, stitched, transcribed, silence-measured and judged
listen  the whole audio of chosen routes stitched at low bitrate, for local listening only
seat    one cast-aware seat reads the weakest seams and says what drags and what lands
report  REPORT.md + flow.json in the run folder: routes ranked by flow, weakest seams, glue-line candidates

Audio of other people's videos is cut locally for listening and never uploaded. See AGENTS.md, "Flow lab".
"""
