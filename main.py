from pathlib import Path
import logging

import click
from tqdm import tqdm

VERBOSITY_LEVELS = ["info", "error", "warn", "debug"]
ANDROID_TIME_MARKER = "checkTimeDrift Android time"
HEARTBEAT_MARKER = "[HMI-SDK](HEARTBEAT)"
SOURCE_EXTENSIONS = ["h", "hpp", "cpp"]

WHITELIST = [
    "route_impl.cpp:",
    "HMI >> NAV",
    "NAV >> HMI",
    "SendOnlineRequest",
    "route_progress_updater",
]

CHANNELS_BLACKLIST = [
    "onboardmap-ndsdataaccess",
    "navigation-instruction-engine",
    "navigation-drivingassistance",
    "MatchingPolylineIndex Source_polyline_index (",
    "traffic",
    "reachable_range_manager",
    "NdsPoiMap",
    "Calculating route ETA for offset",
    "update_task_utility",
    "mapupdate",
    "TrafficEventIterator",
    "DoOnPredictionUpdate",
    "Reachable Range Trigger Manager",
    "OnPredictionUpdate",
    "MapMatcher-NullMapMatcher",
    "main.HarmanAudioControl",
    "NdsLaneTileReader",
    "aggregator-psd-route",
    "main.HarmanHal-Routing",
    "kernel.unknown",
    "VehicleHorizon-PoiCategoryProcessor",
    "lane_segments_builder_impl.cpp:",
    "instruction_tracker",
    "convert_onboard_instruction",
    "instruction",
    "Instruction",
    "task_queue_impl",
    "mapaccess_component",
    "tile",
    "Tile",
    "Dispatcher::",
    "traffic_on_route_tracer.cpp",
    "iterable_arc_buffer",
    "PSD",
    "remaining_consumption_and_range_calculator",
    "MapMatcher-SyncMapDataRequest",
    "45811bf7" "WarningTransmitter",
    "Dispatcher",
    "guidance",
    "parseus",
    "VehicleHorizon",
]


def expect_non_empty(logs):
    if len(logs) == 0:
        raise Exception("The result is empty!")


@click.command("prettify-logs")
@click.argument("in_path", type=Path)
@click.option("-o", "--out_path", type=Path, help="Output path")
@click.option("--start-marker")
@click.option("--stop-marker")
@click.option(
    "--skip-none-time",
    is_flag=True,
    default=True,
    help="Skip records with undefined timestamp",
)
@click.option(
    "--skip-none-channel",
    is_flag=True,
    default=True,
    help="Skip records with undefined channel name",
)
def prettify_logs(
    in_path: Path,
    out_path: Path = None,
    start_marker=None,
    stop_marker=None,
    skip_none_time=True,
    skip_none_channel=True,
    skip_channel=False,
):
    logging.basicConfig(format="%(levelname)s - %(message)s", level=logging.INFO)

    if not in_path.exists():
        logging.fatal(f"Input file is not exists: `{in_path}`")
        return

    assert in_path.exists()
    last_android_time = None
    reached_start_marker = start_marker is None
    reached_stop_marker = False
    out_logs = []
    with in_path.open() as f:
        raw_logs = f.readlines()
        raw_logs_filtered = []
        for msg in tqdm(raw_logs, "Applying channels filtering..."):
            if not any(
                blacklisted_tag in msg for blacklisted_tag in CHANNELS_BLACKLIST
            ) or any(whitelisted_tag in msg for whitelisted_tag in WHITELIST):
                raw_logs_filtered.append(msg)

        raw_logs = raw_logs_filtered
        logging.info(f"Log size after whitelisting is {len(raw_logs)}")

        for msg in tqdm(raw_logs, "Parsing the file..."):
            if ANDROID_TIME_MARKER in msg:
                last_android_time = msg.split()[-2]
                continue

            if HEARTBEAT_MARKER in msg:
                last_android_time = msg.split(HEARTBEAT_MARKER)[1].split()[2][:-1][:8]
                continue

            if start_marker is not None and start_marker in msg:
                reached_start_marker = True

            if not reached_start_marker:
                continue

            if stop_marker is not None and stop_marker in msg:
                reached_stop_marker = True
                logging.debug("Reached termination marker.")

            for ext in SOURCE_EXTENSIONS:
                pattern = f".{ext}:"
                if pattern not in msg:
                    continue

                channel = None
                tokens = msg.split()
                for i, token in enumerate(tokens):
                    if token.lower() in VERBOSITY_LEVELS:
                        channel = tokens[i - 2]

                if channel is None and skip_none_channel and not skip_channel:
                    logging.debug("Channel is none")
                    continue
                if last_android_time is None and skip_none_time:
                    logging.debug("No android time")
                    continue

                space = " "
                msg = space.join(msg.split())
                msg = msg[msg[: msg.find(pattern)].rfind(space) + 1 :]
                content = space.join(msg.split()[1:])
                if len(content) == 0:
                    continue

                if not skip_channel:
                    msg = f"{last_android_time}  {channel: <50}  {f'{msg.split()[0]: <25} {content}'}"
                else:
                    msg = f"{last_android_time}  {f'{msg.split()[0]: <25} {content}'}"

                msg += "\n"
                out_logs.append(msg)

            if reached_stop_marker:
                break

    expect_non_empty(out_logs)

    if not reached_stop_marker and stop_marker is not None:
        logging.warning("Stop marker is unreachable.")

    if out_path is None:
        out_path = Path(
            ".".join(in_path.as_posix().split(".")[:-1]) + "_prettified.log"
        )
        logging.info(f"Output path: {out_path}")

    if out_path.is_dir():
        out_path = out_path / in_path.name.replace(".log", "_prettified.log")
        logging.info(f"Output path: {out_path}")

    if out_path.exists():
        logging.warning("Overwriting existing file!")

    zipped_logs = out_logs[:1]
    expect_non_empty(zipped_logs)
    for msg in out_logs[1:]:

        def clip_message(msg):
            return " ".join(msg.split()[1:])

        if clip_message(zipped_logs[-1]) != clip_message(msg):
            zipped_logs.append(msg)

    expect_non_empty(zipped_logs)
    out_logs = zipped_logs
    logging.info(f'Log size after "zipping" is {len(out_logs)}')

    logging.info(f"Storing results to {out_path}")
    with out_path.open("w") as f:
        f.writelines(out_logs)
