# Homepage Performance Test (JMeter)

## Scope
- Target endpoint: `GET /login`
- Concurrency levels: 10, 20, 50, 100 users
- Metrics: Average response time, Min response time, Max response time, Error %

Additional plan:
- `GET /detect` page-only pressure test (no call to `/api/detect`)

## Files
- `aigc_web/perf/homepage_load_test.jmx`
- `aigc_web/perf/detect_page_only_load_test.jmx`
- `aigc_web/perf/run_perf.ps1`（一键脚本，路径按脚本位置自动推导）

## 1) Start service
在项目根目录（包含 `aigc_web/` 的 `web/` 目录）执行。所有路径均为相对路径，命令行不再写死盘符：

```powershell
python -m pip install -r requirements.txt
python run.py 127.0.0.1:8000
```

## 2) Run JMeter in non-GUI mode
JMeter 路径不再写死：优先使用环境变量 `JMETER_BIN`，其次使用 `PATH` 中的 `jmeter`，最后回退到 `C:\apache-jmeter-5.6.3\bin\jmeter.bat`。

```powershell
$env:JMETER_BIN = "C:\apache-jmeter-5.6.3\bin\jmeter.bat"
.\aigc_web\perf\run_perf.ps1               # GET /login
.\aigc_web\perf\run_perf.ps1 detect-page   # GET /detect
```

等价的手工命令（在项目根目录执行）：

```powershell
$JMETER = $env:JMETER_BIN
& $JMETER -n -t .\aigc_web\perf\homepage_load_test.jmx -l .\aigc_web\perf\results.jtl -e -o .\aigc_web\perf\report
& $JMETER -n -t .\aigc_web\perf\detect_page_only_load_test.jmx -l .\aigc_web\perf\results_detect_page.jtl -e -o .\aigc_web\perf\report_detect_page
```

## 3) Check report
Open:
- `aigc_web/perf/report/index.html`
- `aigc_web/perf/report_detect_page/index.html`

Main charts/tables:
- Statistics (avg/min/max/error%)
- Response Times Over Time
- Active Threads Over Time

## Notes
- Thread groups run sequentially (10 -> 20 -> 50 -> 100), so results can be compared by group name.
- JMeter 的 `-o` 输出目录必须不存在或为空，重复压测前请先删除旧的 `report/`、`report_detect_page/`。
- If you want stricter real-time behavior, reduce ramp-up for each group.
- If your homepage changes to `/`, keep sampler path as `/login` or update assertion rules for 302 redirect.
