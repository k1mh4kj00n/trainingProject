# ==============================================================================
# [NIRS VOT Analysis Script with 5s Smoothing]
# 작성자: 코딩하는 김재혁
# 기능: 데이터 로드 -> 전처리 -> 5초 스무딩 -> 구간 설정 -> 지표 산출 -> 리포트/저장
# ==============================================================================

# 1. 패키지 로드 (없으면 설치)
pkg_list <- c("readxl", "dplyr", "lubridate", "stringr", "zoo", "ggplot2", "writexl", "purrr")
new_pkgs <- pkg_list[!(pkg_list %in% installed.packages()[, "Package"])]
if(length(new_pkgs)) install.packages(new_pkgs)

library(readxl)
library(dplyr)

library(lubridate)
library(stringr)
library(zoo)     # 이동평균용
library(ggplot2)
library(writexl)
library(purrr)

# ==============================================================================
# 2. 데이터 로드 및 전처리 (날짜/시간 파싱 + 스무딩)
# ==============================================================================

cat("▶ 분석할 엑셀 파일을 선택해주세요...\n")
fp <- file.choose()

# 1) 파일 읽기 (모두 텍스트로 읽어 형변환 오류 방지)
raw <- read_excel(fp, skip = 3, col_types = "text")

# 2) 1차 클렌징 (Date, Time, SmO2 추출)
df <- raw %>%
  select(date = 1, time = 2, SmO2_live = 3) %>%
  mutate(
    date = str_trim(as.character(date)),
    time = str_trim(as.character(time)),
    time = str_squish(str_replace_all(time, c("오전" = "AM", "오후" = "PM"))),
    SmO2_live = suppressWarnings(as.numeric(str_replace_all(SmO2_live, "[^0-9\\.]", "")))
  ) %>%
  filter(!is.na(SmO2_live))

# 3) 날짜/시간 파싱 로직
is_numeric_like <- function(x) { !is.na(suppressWarnings(as.numeric(x))) }

# [Date]
date_vec <- rep(NA_real_, nrow(df))
date_is_num <- is_numeric_like(df$date)
date_vec[date_is_num] <- as.numeric(df$date[date_is_num])
date_date <- as.Date(date_vec, origin = "1899-12-30")

need_date_str <- is.na(date_date) & !is.na(df$date)
if (any(need_date_str)) {
  date_date[need_date_str] <- suppressWarnings(ymd(df$date[need_date_str]))
}

# [Time]
time_sec <- rep(NA_real_, nrow(df))
time_is_num <- is_numeric_like(df$time)
time_sec[time_is_num] <- as.numeric(df$time[time_is_num]) * 86400

parse_time_str <- function(v) {
  fmts <- c("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M")
  for (fmt in fmts) {
    tt <- suppressWarnings(strptime(v, format = fmt, tz = "Asia/Seoul"))
    if (!all(is.na(tt))) return(tt)
  }
  return(strptime(rep(NA_character_, length(v)), format = "%H:%M:%S"))
}

need_time_str <- is.na(time_sec) & !is.na(df$time)
if (any(need_time_str)) {
  tt <- parse_time_str(df$time[need_time_str])
  time_sec[need_time_str] <- as.numeric(tt$hour)*3600 + as.numeric(tt$min)*60 + as.numeric(tt$sec)
}

# 4) Datetime 통합 및 0.5초 격자 정렬
datetime_raw <- as.POSIXct(date_date, tz = "Asia/Seoul") + time_sec - hours(9)
df$datetime_raw <- datetime_raw

df <- df %>%
  arrange(datetime_raw) %>%
  group_by(datetime_raw) %>%
  mutate(.dup_idx = row_number() - 1,
         datetime = datetime_raw + dseconds(0.5 * .dup_idx)) %>%
  ungroup() %>%
  select(date, time, SmO2_live, datetime) %>%
  filter(!is.na(datetime))

# ------------------------------------------------------------------------------
# [중요] 5초 이동평균 (Smoothing) 적용
# ------------------------------------------------------------------------------
# 데이터 샘플링 간격 계산
avg_diff <- mean(diff(as.numeric(df$datetime)), na.rm = TRUE)
if(is.na(avg_diff) || avg_diff == 0) avg_diff <- 1

# 5초 윈도우 크기 계산 (홀수로 맞춰 Center 정렬 최적화)
window_size <- round(5 / avg_diff)
if (window_size %% 2 == 0) window_size <- window_size + 1

df <- df %>%
  mutate(
    SmO2_raw = SmO2_live,  # 원본 백업
    # align="center"로 시차(Lag) 방지. 분석 코드는 'SmO2_live'를 참조하므로 덮어씌움.
    SmO2_live = zoo::rollmean(SmO2_live, k = window_size, fill = NA, align = "center")
  ) %>%
  filter(!is.na(SmO2_live)) # 스무딩으로 인한 양 끝 결측 제거

cat(sprintf("▶ 전처리 및 스무딩 완료 (Window: %d samples)\n", window_size))


# ==============================================================================
# 3. 분석 함수 정의 (기존 로직 유지)
# ==============================================================================

# 시간 입력 파서
.parse_time_input <- function(x, anchor_date) {
  tz <- "Asia/Seoul"
  if (inherits(x, "POSIXt")) {
    with_tz(as.POSIXct(x), tz = tz)
  } else {
    x <- str_trim(x)
    ans <- as.POSIXct(paste(anchor_date, x), format = "%Y-%m-%d %H:%M:%OS", tz = tz)
    if (is.na(ans)) stop("시간 파싱 실패: ", x)
    ans
  }
}

# 구간 설정 메인 함수
set_analysis_windows <- function(df, start_time, inflate_time, deflate_time, end_time) {
  anchor_date <- as.Date(df$datetime[1], tz = "Asia/Seoul")
  s <- .parse_time_input(start_time, anchor_date)
  i <- .parse_time_input(inflate_time, anchor_date)
  d <- .parse_time_input(deflate_time, anchor_date)
  e <- .parse_time_input(end_time, anchor_date)
  
  if (!(s < i && i < d && d < e)) stop("시간 순서 오류: start < inflate < deflate < end 이어야 합니다.")
  
  out <- df %>%
    filter(datetime >= s, datetime <= e) %>%
    mutate(
      phase = case_when(
        datetime < i ~ "start→inflate",
        datetime >= i & datetime < d ~ "inflate→deflate",
        TRUE ~ "deflate→end"
      ),
      phase_start = case_when(
        phase == "start→inflate" ~ s,
        phase == "inflate→deflate" ~ i,
        phase == "deflate→end" ~ d
      ),
      t_rel_sec = as.numeric(difftime(datetime, phase_start, units = "secs"))
    )
  
  list(data = out, anchors = list(s=s, i=i, d=d, e=e))
}


# ==============================================================================
# 4. 실행 및 지표 산출
# ==============================================================================

# ▼▼▼ [사용자 입력 영역] 시간 설정 (HH:MM:SS) ▼▼▼
# 실제 엑셀 데이터를 보고 시간을 수정하세요.
input_start   <- "17:20:00"
input_inflate <- "17:21:00"
input_deflate <- "17:26:00"
input_end     <- "17:29:00"
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

# 1) 구간 설정 실행
res <- set_analysis_windows(df, input_start, input_inflate, input_deflate, input_end)
res_data <- res$data
anchors  <- res$anchors

# 2) 지표 산출을 위한 데이터 추출
# Baseline
base_val <- res_data %>% 
  filter(phase == "start→inflate", t_rel_sec >= 0, t_rel_sec <= 60) %>% 
  summarise(m = mean(SmO2_live, na.rm=TRUE)) %>% pull(m)

# 전체 데이터 정렬 (보간용)
df_sorted <- res_data %>% arrange(datetime)
x_all <- as.numeric(df_sorted$datetime)
y_all <- df_sorted$SmO2_live
ok <- is.finite(x_all) & is.finite(y_all)
x_all <- x_all[ok]; y_all <- y_all[ok]

# -------------------------------------------------------
# Slope 1 (Desaturation)
# -------------------------------------------------------
get_slope <- function(t_start, duration) {
  t0 <- anchors$i + seconds(t_start)
  t1 <- anchors$i + seconds(t_start + duration)
  tmp <- res_data %>% filter(datetime >= t0, datetime <= t1)
  if(nrow(tmp) < 2) return(NA)
  coef(lm(SmO2_live ~ t_rel_sec, data = tmp))[2]
}
slope1_0_60   <- get_slope(0, 60)
slope1_30_150 <- get_slope(30, 120) # 30~150s

# -------------------------------------------------------
# Oxygen Deficit (AUC under baseline during occlusion)
# -------------------------------------------------------
t_occ_grid <- sort(unique(c(as.numeric(anchors$i), 
                            x_all[x_all >= as.numeric(anchors$i) & x_all <= as.numeric(anchors$d)], 
                            as.numeric(anchors$d))))
y_occ_grid <- approx(x_all, y_all, xout=t_occ_grid)$y
f_def <- pmax(base_val - y_occ_grid, 0)
oxy_def <- sum((head(f_def,-1) + tail(f_def,-1))/2 * diff(t_occ_grid))

# -------------------------------------------------------
# Min, Peak, Magnitude
# -------------------------------------------------------
# Min (Occlusion phase)
occ_data <- res_data %>% filter(phase == "inflate→deflate")
min_sto2 <- min(occ_data$SmO2_live, na.rm=TRUE)
min_time <- occ_data$datetime[which.min(occ_data$SmO2_live)]

# Peak (Reperfusion phase)
rep_data <- res_data %>% filter(phase == "deflate→end")
peak_sto2 <- max(rep_data$SmO2_live, na.rm=TRUE)
peak_time <- rep_data$datetime[which.max(rep_data$SmO2_live)]

mag <- peak_sto2 - min_sto2

# -------------------------------------------------------
# Slope 2 (Resaturation)
# -------------------------------------------------------
get_slope2 <- function(dur) {
  t1 <- anchors$d + seconds(dur)
  tmp <- res_data %>% filter(datetime >= anchors$d, datetime <= t1)
  if(nrow(tmp) < 2) return(NA)
  coef(lm(SmO2_live ~ t_rel_sec, data = tmp))[2]
}
slope2_10 <- get_slope2(10)
slope2_30 <- get_slope2(30)

# -------------------------------------------------------
# Reperfusion Time (T50, T95) - 보간법 사용
# -------------------------------------------------------
find_time_crossing <- function(target) {
  # min_time 이후부터 탐색
  sub_x <- x_all[x_all >= as.numeric(min_time) & x_all <= as.numeric(anchors$e)]
  sub_y <- y_all[x_all >= as.numeric(min_time) & x_all <= as.numeric(anchors$e)]
  
  if(length(sub_x) < 2) return(NA)
  for(k in 1:(length(sub_x)-1)) {
    if(sub_y[k] <= target && sub_y[k+1] >= target) {
      # 선형 보간으로 정확한 x 찾기
      return(sub_x[k] + (target - sub_y[k])*(sub_x[k+1]-sub_x[k])/(sub_y[k+1]-sub_y[k]))
    }
  }
  return(NA)
}

t50_val <- min_sto2 + 0.5 * mag
t95_val <- min_sto2 + 0.95 * mag

time_50_abs <- find_time_crossing(t50_val)
time_95_abs <- find_time_crossing(t95_val)

rep_time_50 <- if(!is.na(time_50_abs)) time_50_abs - as.numeric(anchors$d) else NA
rep_time_95 <- if(!is.na(time_95_abs)) time_95_abs - as.numeric(anchors$d) else NA

# -------------------------------------------------------
# Reperfusion AUC (Hyperemia)
# -------------------------------------------------------
calc_auc <- function(win_sec) {
  tend <- min(anchors$d + seconds(win_sec), anchors$e)
  g_x <- sort(unique(c(as.numeric(anchors$d), 
                       x_all[x_all >= as.numeric(anchors$d) & x_all <= as.numeric(tend)], 
                       as.numeric(tend))))
  if(length(g_x)<2) return(NA)
  g_y <- approx(x_all, y_all, xout=g_x)$y
  f_pos <- pmax(g_y - base_val, 0)
  sum((head(f_pos,-1)+tail(f_pos,-1))/2 * diff(g_x)) / 60 # min 단위 변환
}

auc_180 <- calc_auc(180)

# ==============================================================================
# 5. 결과 리포트 및 시각화
# ==============================================================================

# 1) 결과 테이블 생성
final_summary <- tibble(
  Item = c("Baseline SmO2", "Slope1 (0-60s)", "Slope1 (30-150s)", 
           "Oxy Deficit (%*s)", "Min SmO2", "Peak SmO2", "Magnitude",
           "Slope2 (0-10s)", "Slope2 (0-30s)", 
           "T50 (s)", "T95 (s)", "AUC (3min, %*min)"),
  Value = c(base_val, slope1_0_60, slope1_30_150, 
            oxy_def, min_sto2, peak_sto2, mag,
            slope2_10, slope2_30, 
            rep_time_50, rep_time_95, auc_180)
)

print(final_summary)

# 2) 그래프 그리기 (Area Filled) [수정됨]
p <- ggplot(res_data, aes(x = datetime)) +
  
  # --- [1] Oxygen Deficit (Red Ribbon) ---
  # 조건 1: 구간은 inflate ~ deflate 사이
  # 조건 2: ymin = 실제값(또는 Base보다 높으면 Base로 제한), ymax = Base
  # 결과: Base보다 '낮은' 영역만 채워짐
  geom_ribbon(
    data = subset(res_data, datetime >= anchors$i & datetime <= anchors$d),
    aes(ymin = pmin(SmO2_live, base_val), ymax = base_val),
    fill = "red", alpha = 0.3
  ) +
  
  # --- [2] Reperfusion AUC (Green Ribbon) ---
  # 조건 1: 구간은 deflate ~ end 사이 (사용자 요청 반영)
  # 조건 2: ymin = Base, ymax = 실제값(또는 Base보다 낮으면 Base로 제한)
  # 결과: Base보다 '높은' 영역만 채워짐
  geom_ribbon(
    data = subset(res_data, datetime >= anchors$d & datetime <= anchors$e),
    aes(ymin = base_val, ymax = pmax(SmO2_live, base_val)),
    fill = "green", alpha = 0.3
  ) +
  
  # --- [3] 데이터 라인 (Raw & Smoothed) ---
  geom_line(aes(y = SmO2_raw, color="Raw"), alpha=0.3) +    # 흐린 원본
  geom_line(aes(y = SmO2_live, color="Smoothed"), size=1) + # 진한 스무딩
  
  # --- [4] 주요 포인트 및 라인 ---
  geom_hline(yintercept = base_val, linetype="dashed", color="black") +
  geom_vline(xintercept = as.numeric(c(anchors$s, anchors$i, anchors$d, anchors$e)), 
             linetype="dotted", color="grey30") +
  
  geom_point(aes(x=min_time, y=min_sto2), color="blue", size=3) +
  geom_point(aes(x=peak_time, y=peak_sto2), color="red", size=3) +
  
  scale_color_manual(values = c("Raw"="grey50", "Smoothed"="black")) +
  labs(title = "NIRS VOT Analysis (Area Filled)", 
       subtitle = "Red: Oxygen Deficit (Below Base) / Green: Hyperemia (Above Base)",
       y = "SmO2 (%)", x = "Time") +
  theme_minimal()

print(p)

# ------------------------------------------------------------------------------
# 3) [수정됨_V2] 엑셀 저장 (경로 오류 수정)
# ------------------------------------------------------------------------------
# 기본 파일명 생성
default_filename <- paste0("NIRS_VOT_Result_", format(Sys.time(), "%Y%m%d_%H%M%S"), ".xlsx")

# 저장 대화상자 띄우기
# (참고: 반환되는 객체는 단순 문자열이 아니라 tclObj입니다)
raw_path_obj <- tcltk::tkgetSaveFile(
  title = "결과 엑셀 파일 저장 위치 선택",
  filetypes = "{{Excel Files} {.xlsx}}", 
  defaultextension = ".xlsx",
  initialfile = default_filename
)

# [중요] tclObj를 R의 문자열(String)로 정확히 변환하기 위해 tclvalue() 사용
save_path <- tcltk::tclvalue(raw_path_obj)

# 경로가 비어있지 않은지 확인 (nzchar는 문자열이 비었는지(FALSE) 아닌지(TRUE) 확인하는 함수)
if (nzchar(save_path)) {
  
  # 엑셀 저장 실행
  writexl::write_xlsx(final_summary, path = save_path)
  
  message("✅ 저장 성공! 파일 경로: ", save_path)
  
  # 윈도우라면 저장된 폴더 열어주기
  if (.Platform$OS.type == "windows") {
    tryCatch(shell.exec(dirname(save_path)), error = function(e) NULL)
  }
  
} else {
  message("❌ 저장이 취소되었습니다. (경로가 선택되지 않음)")
}

