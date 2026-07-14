# Emovision Streaming Backend

Emovision Streaming 是一個基於 Docker Compose 構建的高度可擴展的影像串流與非同步處理後端微服務叢集。其主要職責為接收前端的影像/影片資料流、透過工作佇列 (Message Queue) 進行耗時的情緒與視覺特徵提取，並可透過 WebSocket 即時回傳分析結果。

---

## 程式功能分析 (Program Feature Analysis)

整個系統由多個互相獨立的 Docker 容器服務組成：

1. **核心 API 服務 (`api` & `videoapi`)**
   * **`api` 服務**：使用 Python (Flask/WSGI) 撰寫，透過 `uWSGI` 以 Gevent 模式運行，並開啟了 `--http-websockets` 支援。主要負責處理即時串流 (Streaming) 與前端的長連線雙向通訊。
   * **`videoapi` 服務**：專門處理影片檔案的上傳、管理，並提供後續排程分析的 RESTful API 接口。
2. **非同步任務與訊息佇列 (`worker`, `monitor`, `redis`)**
   * 採用 **Redis** 作為 Message Broker。
   * **`worker` 服務**：執行 Celery Worker，訂閱 Redis 上的任務，負責將消耗大量運算資源的影片拆解、分析與轉檔工作移出主 API 執行緒。
   * **`monitor` 服務**：啟動 `Flower`，提供網頁版的 Celery 叢集監控面板（對外 Port `7055`），方便開發者隨時掌握任務的處理進度與 Worker 狀態。
3. **閘道與反向代理 (`nginx`, `loadbalancer`, `gateway`)**
   * **`nginx`**：負責作為靜態檔案與部分 API 的反向代理（對外 Port `7080`）。
   * **`gateway` 與 `loadbalancer`**：作為整體微服務的入口點（對外 Port `5001`），統籌路由派發與多個 API 容器間的負載平衡。

---

## 檔案與目錄結構 (Directory Structure)

專案結構完全依照 Docker Compose 的微服務劃分：

```text
emovision-streaming/
├── docker-compose.yml   # 核心架構藍圖：定義 8 個服務、內部網路 (web_nw) 與共用 Volume
├── api/                 # Streaming 即時串流處理服務 (Python/uWSGI/WebSockets)
├── videoapi/            # 處理影片上傳與 REST API 的服務
├── queue/               # Celery Worker 與任務邏輯定義檔
├── nginx/               # Nginx 設定檔與 Dockerfile
├── gateway/             # API 閘道器邏輯
├── load-balancer/       # 負載平衡器設定
├── ffmpeg/              # 影像轉檔與切割處理腳本
└── sync.sh              # 伺服器端部署或檔案同步用的腳本
```

---

## 使用到的 Design Pattern 與架構決策

1. **Microservices Architecture (微服務架構)**
   * 將系統嚴格劃分為：串流、影片處理、任務佇列、監控、閘道器。這使得若影像分析負載過重時，可以單獨將 `worker` 服務進行橫向擴展 (Scale-out)。
2. **Asynchronous Task Queue (非同步任務佇列模式)**
   * **決策**：影像分析極度耗時，絕對不能在 HTTP Request/Response 的生命週期內完成。
   * **實作**：使用 `Redis` + `Celery`。`videoapi` 收到影片後立即回應 200 OK，並將處理任務推入 Redis；`worker` 隨後在背景拉取任務並使用 `FFmpeg` 等工具慢慢處理。
3. **API Gateway Pattern (閘道器模式)**
   * 客戶端不需知道後端叢集長什麼樣子，統一透過 `loadbalancer` (`5001`) 或 `nginx` (`7080`) 進入，由 Gateway 處理路由分發。

---

## 專案亮點介紹 (Highlights)

* ⚡️ **高併發的 WebSocket 串流設計**
  * `api` 容器在啟動指令中使用了 `uwsgi --gevent 100 --http-websockets`。透過 Gevent 協程 (Coroutine) 技術，單一 Python 程序即可同時支撐大量且低開銷的即時視訊/數據連線。
* 🐳 **一鍵式的容器化部署與共用儲存**
  * 完美利用了 Docker Volumes (`api_data`, `db_data`) 實現容器間的資料共享。例如：`videoapi` 將使用者上傳的影片存入 `api_data`，而背景的 `worker` 與 `nginx` 都能透過掛載同一個 Volume 直接讀取並處理該檔案，避免了網路傳輸的延遲。
* 👁 **內建完善的維運監控系統**
  * 直接把 `Flower` 封裝在 `monitor` 容器內，將系統監控「代碼化 (Infrastructure as Code)」，讓團隊能視覺化監控 Redis 佇列中的任務成功與失敗率。
