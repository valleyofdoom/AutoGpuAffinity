import argparse
import csv
import ctypes
import datetime
import logging
import os
import shutil
import subprocess
import sys
import textwrap
import time
import traceback
import winreg
from typing import NoReturn

import consts
import framerate
import psutil
import setupapi
import wmi
from config import Api, Config

LOG_CLI = logging.getLogger("CLI")


def start_afterburner(path: str, profile: int) -> None:
    with subprocess.Popen([path, f"/Profile{profile}", "/Q"]) as process:
        time.sleep(5)
        process.kill()


def set_driver_state(hwid: str, state: int) -> int:
    device_info_handle = setupapi.SetupDiGetClassDevsW(
        None, ctypes.c_wchar_p(hwid), None, setupapi.DIGCF_ALLCLASSES | setupapi.DIGCF_DEVICEINTERFACE
    )

    if device_info_handle == -1:
        LOG_CLI.error(f"SetupDiGetClassDevsW failed: {ctypes.GetLastError()}")
        return 1

    dev_info_data = setupapi.SP_DEVINFO_DATA()
    dev_info_data.cbSize = ctypes.sizeof(setupapi.SP_DEVINFO_DATA)

    if not setupapi.SetupDiEnumDeviceInfo(device_info_handle, 0, ctypes.byref(dev_info_data)):
        LOG_CLI.error(f"SetupDiEnumDeviceInfo failed: {ctypes.GetLastError()}")
        return 1

    params = setupapi.SP_PROPCHANGE_PARAMS()

    params.ClassInstallHeader.cbSize = ctypes.sizeof(params.ClassInstallHeader)
    params.ClassInstallHeader.InstallFunction = setupapi.DIF_PROPERTYCHANGE
    params.StateChange = state
    params.Scope = setupapi.DICS_FLAG_GLOBAL
    params.HwProfile = 0

    if not setupapi.SetupDiSetClassInstallParamsA(
        device_info_handle,
        ctypes.byref(dev_info_data),
        ctypes.byref(params.ClassInstallHeader),
        ctypes.sizeof(params),
    ):
        LOG_CLI.error(f"SetupDiSetClassInstallParamsA failed: {ctypes.GetLastError()}")
        return 1

    if not setupapi.SetupDiCallClassInstaller(
        setupapi.DIF_PROPERTYCHANGE, device_info_handle, ctypes.byref(dev_info_data)
    ):
        LOG_CLI.error(f"SetupDiCallClassInstaller failed: {ctypes.GetLastError()}")
        return 1

    return 0


def restart_driver(hwid: str) -> int:
    if set_driver_state(hwid, setupapi.DICS_DISABLE) != 0:
        LOG_CLI.error("failed to disable driver while restarting")
        return 1

    time.sleep(2)

    if set_driver_state(hwid, setupapi.DICS_ENABLE) != 0:
        LOG_CLI.error("failed to enable driver while restarting")
        return 1

    time.sleep(2)

    return 0


def apply_affinity(hwids: list[str], cpu: int = -1, apply: bool = True) -> int:
    for hwid in hwids:
        policy_path = f"SYSTEM\\ControlSet001\\Enum\\{hwid}\\Device Parameters\\Interrupt Management\\Affinity Policy"

        if apply and cpu > -1:
            decimal_affinity = 1 << cpu
            bin_affinity = bin(decimal_affinity).lstrip("0b")
            le_hex = int(bin_affinity, 2).to_bytes(8, "little").rstrip(b"\x00")

            with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, policy_path) as key:
                winreg.SetValueEx(key, "DevicePolicy", 0, winreg.REG_DWORD, 4)
                winreg.SetValueEx(
                    key,
                    "AssignmentSetOverride",
                    0,
                    winreg.REG_BINARY,
                    le_hex,
                )

        else:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    policy_path,
                    0,
                    winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY,
                ) as key:
                    winreg.DeleteValue(key, "DevicePolicy")
                    winreg.DeleteValue(key, "AssignmentSetOverride")
            except FileNotFoundError:
                LOG_CLI.debug("affinity policy has already been removed for %s", hwid)

        if restart_driver(hwid) != 0:
            LOG_CLI.error("failed to restart driver")
            return 1

    return 0


def print_table(formatted_results: dict[str, dict[str, str]]):
    # print table headings
    print(f"{'CPU':<5}", end="")

    for metric in (
        "Max",
        "Avg",
        "Min",
        "STDEV",
        "1 %ile",
        "0.1 %ile",
        "0.01 %ile",
        "0.005 %ile",
        "1% Low",
        "0.1% Low",
        "0.01% Low",
        "0.005% Low",
    ):
        print(f"{metric:<12}", end="")

    print()  # new line

    # print values for each heading
    for _cpu, _results in formatted_results.items():
        print(f"{_cpu:<5}", end="")
        for metric_value in _results.values():
            # padding needs to be larger to compensate for color chars
            right_padding = 21 if "[" in metric_value else 12
            print(f"{metric_value:<{right_padding}}", end="")

        print()  # new line

    print()  # new line


def display_results(csv_directory: str, enable_color: bool) -> None:
    results: dict[str, dict[str, float]] = {}

    # each index represents the rank (e.g. index 0 is 1st)
    colors: list[str] = [
        "\x1b[92m",  # Green
        "\x1b[93m",  # Yellow
    ]

    if enable_color:
        default = "\x1b[0m"
        os.system("color")
    else:
        default = ""

    cpus = sorted([int(file.strip("CPU-.csv")) for file in os.listdir(csv_directory)])
    num_cpus = len(cpus)
    # 1 CPUs means no ranking will be done
    # 2 CPUs means only one metric will be ranked since it can be either or
    # always leave last place unranked

    top_n_values = num_cpus - 1 if num_cpus < 3 else len(colors)

    for cpu in cpus:
        csv_file = f"CPU-{cpu}.csv"

        frametimes: list[float] = []

        with open(f"{csv_directory}\\{csv_file}", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                # convert key names to lowercase because column names changed in a newer version of PresentMon
                row_lower = {key.lower(): value for key, value in row.items()}

                if (ms_between_presents := row_lower.get("msbetweenpresents")) is not None:
                    frametimes.append(float(ms_between_presents))

        fps = framerate.Fps(frametimes)

        # results of current CPU in results dict
        results[str(cpu)] = {
            "maximum": round(fps.maximum(), 2),
            "average": round(fps.average(), 2),
            "minimum": round(fps.minimum(), 2),
            # negate positive value so that highest negative value will be the lowest absolute value
            "stdev": round(-fps.stdev(), 2),
            **{
                f"{metric}{value}": round(getattr(fps, metric)(value), 2)
                for metric in ("percentile", "lows")
                for value in (1, 0.1, 0.01, 0.005)
            },
        }

    formatted_results: dict[str, dict[str, str]] = {cpu: {} for cpu in results}

    # analyze best values for each metric
    for metric in (
        "maximum",
        "average",
        "minimum",
        "stdev",
        # "percentile1", "percentile0.1" etc
        *(tuple(f"{metric}{value}" for metric in ("percentile", "lows") for value in (1, 0.1, 0.01, 0.005))),
    ):
        # set of all values within the metric
        values = {_results[metric] for _results in results.values()}

        # create ordered list without duplicates of top n values
        top_values = list(dict.fromkeys(sorted(values, reverse=True)[:top_n_values]))

        for _cpu, _results in results.items():
            metric_value = _results[metric]

            # abs is for negative values such as stdev
            # :.2f is for .00 numerical formatting
            new_value = f"{abs(metric_value):.2f}"

            # determine rank of value
            if enable_color:
                try:
                    nth_best = top_values.index(metric_value)
                    color = colors[nth_best]
                    new_value = f"{color}{new_value}{default}"
                except ValueError:
                    # don't highlight value as top n by leaving it unmodified
                    pass

            formatted_results[_cpu][metric] = new_value

    os.system("<nul set /p=\x1b[8;50;1000t")

    print_table(formatted_results)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--version",
        action="version",
        version=f"AutoGpuAffinity v{consts.VERSION}",
    )
    parser.add_argument(
        "--config",
        metavar="<config>",
        type=str,
        help="path to config file",
    )
    parser.add_argument(
        "--analyze",
        metavar="<csv directory>",
        type=str,
        help="analyze csv files from a previous benchmark",
    )
    parser.add_argument(
        "--apply-affinity",
        metavar="<cpu>",
        type=int,
        help="assign a single core affinity to graphics drivers",
    )

    return parser.parse_args()


def is_admin() -> bool:
    return ctypes.windll.shell32.IsUserAnAdmin()


def kill_processes(*targets: str) -> None:
    targets_set = set(targets)

    for process in psutil.process_iter():
        if process.name().lower() in targets_set:
            process.kill()


def main() -> int:
    logging.basicConfig(format="[%(name)s] %(levelname)s: %(message)s", level=logging.INFO)

    print(
        f"AutoGpuAffinity Version {consts.VERSION} - GPLv3\nGitHub - https://github.com/valleyofdoom\n",
    )

    if not is_admin():
        LOG_CLI.error("administrator privileges required")
        return 1

    full_program_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__)
    os.chdir(full_program_dir)

    args = parse_args()

    winver = sys.getwindowsversion()

    hwids_gpu: list[str] = [gpu.PnPDeviceID for gpu in wmi.WMI().Win32_VideoController()]

    if not hwids_gpu:
        LOG_CLI.error("no graphics cards found")
        return 1

    cpu_count = os.cpu_count()
    if cpu_count is None:
        LOG_CLI.error("failed to get CPU cores count")
        return 1

    cpu_count -= 1  # adjust for zero-based indexing

    if args.analyze:
        display_results(args.analyze, winver.major >= 10)
        return 0

    bd_start = None
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            "SYSTEM\\CurrentControlSet\\Services\\BasicDisplay",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            bd_start = winreg.QueryValueEx(key, "Start")[0]
    except FileNotFoundError:
        pass

    if bd_start is None:
        LOG_CLI.error("unable to get BasicDisplay start type")
        return 1

    if bd_start == 4:
        LOG_CLI.error(
            "enable the BasicDisplay driver to prevent issues with restarting the GPU driver",
        )
        return 1

    if args.apply_affinity:
        if not 0 <= args.apply_affinity <= cpu_count:
            LOG_CLI.error("invalid affinity specified %d", args.apply_affinity)
            return 1

        if apply_affinity(hwids_gpu, args.apply_affinity) != 0:
            LOG_CLI.error(f"failed to apply affinity to CPU {args.apply_affinity}")
            return 1

        LOG_CLI.info("set gpu driver affinity to: CPU %d", args.apply_affinity)
        return 0

    presentmon_version = "1.10.0" if winver.major >= 10 and winver.product_type != 3 else "1.6.0"
    presentmon_binary = f"PresentMon-{presentmon_version}-x64.exe"

    config_path = args.config if args.config is not None else "config.ini"

    try:
        cfg = Config(config_path)
    except FileNotFoundError as e:
        LOG_CLI.exception(e)
        return 1

    if cfg.validate_config() != 0:
        LOG_CLI.error("failed to validate config")
        return 1

    api_binpaths: dict[Api, str] = {
        Api.LIBLAVA: "bin\\liblava\\lava-triangle.exe",
        Api.D3D9: "bin\\D3D9-benchmark.exe",
    }

    api_binpath = api_binpaths[cfg.settings.api]
    api_binname = os.path.basename(api_binpath)

    if cfg.settings.custom_cpus:
        # remove duplicates and sort
        benchmark_cpus = sorted(set(cfg.settings.custom_cpus))

        if not all(0 <= cpu <= cpu_count for cpu in benchmark_cpus):
            LOG_CLI.error("invalid cpus in custom_cpus array")
            return 1
    else:
        benchmark_cpus = list(range(cpu_count + 1))

    session_directory = f"captures\\AutoGpuAffinity-{time.strftime('%d%m%y%H%M%S')}"

    estimated_time_seconds = (
        10
        + cfg.settings.cache_duration
        + cfg.settings.benchmark_duration
        + (5 if cfg.msi_afterburner.profile > 0 else 0)
    ) * len(benchmark_cpus)

    estimated_time = datetime.timedelta(seconds=estimated_time_seconds)
    finish_time = datetime.datetime.now() + estimated_time

    print(
        textwrap.dedent(
            f"""        Session Directory        {session_directory}
        Cache Duration           {cfg.settings.cache_duration}
        Benchmark Duration       {cfg.settings.benchmark_duration}
        Benchmark CPUs           {"All" if not cfg.settings.custom_cpus else ",".join([str(cpu) for cpu in benchmark_cpus])}
        Subject                  {os.path.splitext(api_binname)[0]}
        Estimated Time           {estimated_time}
        Estimated End Time       {finish_time.strftime("%H:%M:%S")}
        Load Afterburner         {cfg.msi_afterburner.profile > 0}
        DPC/ISR Logging          {cfg.xperf.enabled}
        Save ETLs                {cfg.xperf.save_etls}
        Sync Affinity            {cfg.settings.sync_driver_affinity}
        """,
        ),
    )

    if not cfg.settings.skip_confirmation:
        input("press enter to start benchmarking...")

    subject_args: list[str] = []

    if cfg.settings.api == Api.LIBLAVA:
        subject_args = [
            f"--fullscreen={int(cfg.liblava.fullscreen)}",
            f"--width={cfg.liblava.x_resolution}",
            f"--height={cfg.liblava.y_resolution}",
            f"--fps_cap={cfg.liblava.fps_cap}",
            f"--triple_buffering={int(cfg.liblava.triple_buffering)}",
        ]

    # this will create all of the required folders
    os.makedirs(f"{session_directory}\\CSVs", exist_ok=True)

    # stop any existing trace sessions and processes
    if cfg.xperf.enabled:
        os.mkdir(f"{session_directory}\\xperf")

        try:
            subprocess.run(
                [cfg.xperf.location, "-stop"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            # ignore if already stopped
            if e.returncode != 2147946601:
                LOG_CLI.exception(e)
                raise

    kill_processes("xperf.exe", api_binname, presentmon_binary)

    for cpu in benchmark_cpus:
        LOG_CLI.info("benchmarking CPU %d", cpu)

        if apply_affinity(hwids_gpu, cpu) != 0:
            LOG_CLI.error(f"failed to apply affinity to CPU {cpu}")
            return 1

        time.sleep(5)

        if (profile := cfg.msi_afterburner.profile) > 0:
            start_afterburner(cfg.msi_afterburner.location, profile)

        affinity_args: list[str] = []
        if cfg.settings.sync_driver_affinity:
            affinity_args.extend(["/affinity", hex(1 << cpu)])

        subprocess.run(
            ["start", "", *affinity_args, api_binpath, *subject_args],
            shell=True,
            check=True,
        )

        # 5s offset to allow subject to launch
        time.sleep(5 + cfg.settings.cache_duration)

        if cfg.xperf.enabled:
            subprocess.run(
                [cfg.xperf.location, "-on", "base+interrupt+dpc"],
                check=True,
            )

        subprocess.run(
            [
                f"bin\\PresentMon\\{presentmon_binary}",
                "-stop_existing_session",
                "-no_top",
                "-timed",
                str(cfg.settings.benchmark_duration),
                "-process_name",
                api_binname,
                "-output_file",
                f"{session_directory}\\CSVs\\CPU-{cpu}.csv",
                "-terminate_after_timed",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

        if not os.path.exists(f"{session_directory}\\CSVs\\CPU-{cpu}.csv"):
            LOG_CLI.error(
                "csv log unsuccessful, this may be due to a missing dependency or windows component",
            )
            shutil.rmtree(session_directory)
            if apply_affinity(hwids_gpu, apply=False) != 0:
                LOG_CLI.error("failed to reset affinity")
                return 1

            return 1

        if cfg.xperf.enabled:
            subprocess.run(
                [
                    cfg.xperf.location,
                    "-d",
                    f"{session_directory}\\xperf\\CPU-{cpu}.etl",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )

            try:
                subprocess.run(
                    [
                        cfg.xperf.location,
                        "-quiet",
                        "-i",
                        f"{session_directory}\\xperf\\CPU-{cpu}.etl",
                        "-o",
                        f"{session_directory}\\xperf\\CPU-{cpu}.txt",
                        "-a",
                        "dpcisr",
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError:
                LOG_CLI.error("unable to generate dpcisr report")
                shutil.rmtree(session_directory)
                if apply_affinity(hwids_gpu, apply=False) != 0:
                    LOG_CLI.error("failed to reset affinity")
                    return 1  # return 1 after anyway
                return 1

            if not cfg.xperf.save_etls:
                os.remove(f"{session_directory}\\xperf\\CPU-{cpu}.etl")

        kill_processes("xperf.exe", api_binname, presentmon_binary)

    # cleanup
    if apply_affinity(hwids_gpu, apply=False) != 0:
        LOG_CLI.error("failed to reset affinity")
        return 1

    if os.path.exists("C:\\kernel.etl"):
        os.remove("C:\\kernel.etl")

    print()  # new line
    display_results(f"{session_directory}\\CSVs", winver.major >= 10)

    return 0


def _main() -> NoReturn:
    exit_code = 0

    try:
        exit_code = main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception:
        print(traceback.format_exc())
        exit_code = 1
    finally:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        process_array = (ctypes.c_uint * 1)()
        num_processes = kernel32.GetConsoleProcessList(process_array, 1)

        # only pause if script was ran by double-clicking
        if num_processes < 3:
            input("press enter to exit")

        sys.exit(exit_code)


if __name__ == "__main__":
    _main()
