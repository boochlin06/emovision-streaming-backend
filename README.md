# Emovision Streaming Backend

Emovision Streaming 是一個強大的後端微服務架構，專門用來處理影像串流 (Video Streaming)、影像轉檔以及情緒視覺 API 的高併發請求。

---

## 程式功能分析 (Program Feature Analysis)

1. **串流影音處理核心**
   * 結合 `ffmpeg` 進行影片的編解碼、轉檔或是即時影音串流擷取。
2. **反向代理與負載平衡**
   * 透過 `nginx` 與 `load-balancer`，有效分配前端請求至後端不同的 API 容器，確保高併發時的穩定性。
3. **API 服務與非同步佇列**
   * `api` 與 `videoapi` 負責處理商業邏輯與情緒視覺推論的請求。
   * 導入 `queue`（訊息佇列）系統，將耗時的影片處理工作非同步化，避免阻塞主執行緒。

---

## 檔案與目錄結構 (Directory Structure)

```text
emovision-streaming/
├── api/              # 主要業務邏輯 API 微服務
├── videoapi/         # 專門處理影片串流/上傳的 API 微服務
├── ffmpeg/           # FFmpeg 處理腳本與容器設定
├── nginx/            # Nginx 反向代理配置
├── load-balancer/    # 負載平衡器配置
├── queue/            # 訊息佇列服務 (如 RabbitMQ / Redis)
├── gateway/          # API Gateway，統一的請求入口
├── docker-compose.yml# 容器化叢集部署腳本
└── sync.sh           # 輔助的同步/維運腳本
```

---

## 使用到的 Design Pattern

1. **Microservices Architecture (微服務架構)**
   * 將龐大的影片處理系統解耦為 API、Video API、Gateway、Queue 等獨立模組，各司其職且互不干擾。
2. **Pub/Sub (發布-訂閱模式)**
   * 透過 `queue` 系統實作非同步事件驅動機制，API 收到影片後發布任務，由背後的 Worker (FFmpeg) 訂閱並處理。
3. **API Gateway Pattern (閘道器模式)**
   * 使用 Gateway 統一管理所有客戶端的 Request，負責路由轉發、認證與限流。

---

## 專案亮點介紹 (Highlights)

* 🐳 **高度容器化部署 (Docker)**：只需一行指令（透過 `docker-compose.yml`）即可在任何伺服器上還原整個複雜的串流叢集環境。
* 📈 **極佳的橫向擴展性 (Scalability)**：藉由 Load Balancer 與微服務架構，當影像處理需求大增時，能輕易地增加 FFmpeg Worker 或 API 節點來舒緩流量。
