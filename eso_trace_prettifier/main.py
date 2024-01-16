from pathlib import Path
import logging

import click
from tqdm import tqdm

from eso_trace_prettifier.blacklist import DEFAULT_BLACKLIST
from eso_trace_prettifier.whitelist import DEFAULT_WHITELIST

VERBOSITY_LEVELS = ["info", "error", "warn", "debug"]
ANDROID_TIME_MARKER = "checkTimeDrift Android time"
HEARTBEAT_MARKER = "[HMI-SDK](HEARTBEAT)"
SOURCE_EXTENSIONS = ["h", "hpp", "cpp"]

EMPTY_RESULT_MESSAGE = "The result is empty!"


def read_list_from_file(path: Path):
    if path is None:
        return []

    with path.open() as f:
        return f.readlines()


def prettify_logs(
    in_path: Path,
    out_path: Path,
    start_marker,
    stop_marker,
    skip_none_time,
    skip_none_channel,
    skip_channel,
    priority_whitelist_path: Path,
    priority_blacklist_path: Path,
):
    if in_path.is_dir():
        for p in in_path.iterdir():
            prettify_logs(
                p,
                out_path,
                start_marker,
                stop_marker,
                skip_none_time,
                skip_none_channel,
                skip_channel,
                priority_whitelist_path,
                priority_blacklist_path,
            )

        return

    priority_whitelist = read_list_from_file(priority_whitelist_path)
    priority_blacklist = read_list_from_file(priority_blacklist_path)

    last_android_time = None
    reached_start_marker = start_marker is None
    reached_stop_marker = False
    out_logs = []
    with in_path.open() as f:
        raw_logs = f.readlines()
        raw_logs_filtered = []
        for msg in tqdm(raw_logs, "Applying channels filtering..."):
            should_append = not any(
                blacklisted_tag in msg for blacklisted_tag in DEFAULT_BLACKLIST
            ) or any(whitelisted_tag in msg for whitelisted_tag in DEFAULT_WHITELIST)

            if any(tag in msg for tag in priority_blacklist):
                should_append = False

            if any(tag in msg for tag in priority_whitelist):
                should_append = True

            if should_append:
                raw_logs_filtered.append(msg)

        raw_logs = raw_logs_filtered
        logging.debug(f"Log size after whitelisting is {len(raw_logs)}")

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

    if len(out_logs) == 0:
        logging.info(EMPTY_RESULT_MESSAGE)
        return

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
    if len(zipped_logs) == 0:
        logging.info(EMPTY_RESULT_MESSAGE)
        return

    for msg in out_logs[1:]:
        clip_message = lambda message: " ".join(message.split()[1:])
        if clip_message(zipped_logs[-1]) != clip_message(msg):
            zipped_logs.append(msg)

    if len(zipped_logs) == 0:
        logging.info(EMPTY_RESULT_MESSAGE)
        return

    out_logs = zipped_logs
    logging.debug(f'Log size after "zipping" is {len(out_logs)}')

    logging.info(f"Storing results to {out_path}")
    with out_path.open("w") as f:
        f.writelines(out_logs)


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
@click.option("--priority-whitelist-path", type=Path, help="Path to priority whitelist")
@click.option("--priority-blacklist-path", type=Path, help="Path to priority blacklist")
def cli(
    in_path: Path,
    out_path: Path = None,
    start_marker=None,
    stop_marker=None,
    skip_none_time=True,
    skip_none_channel=True,
    skip_channel=False,
    priority_whitelist_path: Path = None,
    priority_blacklist_path: Path = None,
):
    logging.basicConfig(format="%(levelname)s - %(message)s", level=logging.INFO)

    if not in_path.exists():
        logging.fatal(f"Input file is not exists: `{in_path}`")
        return

    if in_path.is_dir():
        for p in in_path.iterdir():
            prettify_logs(
                p,
                out_path,
                start_marker,
                stop_marker,
                skip_none_time,
                skip_none_channel,
                skip_channel,
                priority_whitelist_path,
                priority_blacklist_path,
            )

    else:
        prettify_logs(
            in_path,
            out_path,
            start_marker,
            stop_marker,
            skip_none_time,
            skip_none_channel,
            skip_channel,
            priority_whitelist_path,
            priority_blacklist_path,
        )
