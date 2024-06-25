# AutoGpuAffinity

[![Downloads](https://img.shields.io/github/downloads/valleyofdoom/AutoGpuAffinity/total.svg)](https://github.com/valleyofdoom/AutoGpuAffinity/releases)

<img src="/assets/img/example-output.png" width="1000">

> [!IMPORTANT]
> I am not responsible for damage caused to your computer. There is a risk of your GPU driver not responding after restarting it during the tests. A possible fix for this is to set the PCIe link speed to the maximum supported in BIOS.

## Usage

```
AutoGpuAffinity
GitHub - https://github.com/valleyofdoom

usage: AutoGpuAffinity [-h] [--config <config>] [--analyze <csv directory>] [--apply-affinity <cpu>]

optional arguments:
  -h, --help            show this help message and exit
  --config <config>     path to config file
  --analyze <csv directory>
                        analyze csv files from a previous benchmark
  --apply-affinity <cpu>
                        assign a single core affinity to graphics drivers
```

- Windows Performance Toolkit from the Windows ADK must be installed for DPC/ISR logging with xperf (this is entirely optional)

  - [ADK for Windows 8.1+](https://docs.microsoft.com/en-us/windows-hardware/get-started/adk-install)

  - [ADK for Windows 7](http://download.microsoft.com/download/A/6/A/A6AC035D-DA3F-4F0C-ADA4-37C8E5D34E3D/setup/WinSDKPerformanceToolKit_amd64/wpt_x64.msi)

- Maintain overclock settings with MSI Afterburner throughout the benchmark if applicable

  - Save the desired settings to a profile (e.g. profile 1)

  - Configure the path and profile to load in ``config.ini``

- Download and extract the latest release from the [releases tab](https://github.com/valleyofdoom/AutoGpuAffinity/releases)

- Run **AutoGpuAffinity** through the command-line and press enter when ready to start benchmarking

- After the tool has benchmarked each core, the GPU affinity will be reset to the Windows default and a table will be displayed with the results. Green values indicate the highest value and yellow indicates the second-highest value for a given metric. The xperf report can be found in the session directory

## Analyze Old Sessions

CSV logs can be analyzed at any time by passing the folder of CSVs to the ``--analyze`` argument (example below). This is helpful in situations where the user accidently closes the window as the results are displayed.

```bat
AutoGpuAffinity --analyze ".\captures\AutoGpuAffinity-170523162424\CSVs\"
```

## Standalone Benchmarking

AutoGpuAffinity can be used as a regular benchmark if **custom_cores** is set to a single core in ``config.ini``. If you do not usually configure the GPU driver affinity, the array can be set to ``[0]`` as the graphics kernel typically runs on CPU 0 by default. This results in an automated benchmark that is completely independent to benchmarking the GPU driver affinity. Keep in mind that AutoGpuAffinity resets the affinity policy to the default Windows state once the benchmark has ended (which is no specified affinity) so don't forget to re-configure your affinity policy afterwards again if applicable.
