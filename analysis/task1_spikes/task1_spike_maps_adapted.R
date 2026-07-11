# ============================================================
# Task 1: Enforcement Spike Measure + Descriptive Maps
# Central Valley Immigration Courts Project
# ============================================================
# ADAPTED from Prof. Amuedo-Dorantes' task1_spike_maps.R.
# Changes vs. her file (everything else, incl. the spike
# definition, is untouched):
#   1. Input path: analysis/task1_spikes/detention_county_month.csv.
#      The input was pre-built to her exact expected schema
#      (county_fips, year, month, detention_count), with the grid
#      completed so every county has a row for every month
#      2012-01..2026-03 (zero detentions = 0, not a missing row).
#      Without that completion the 12-row rolling window spans
#      more than 12 calendar months for sparse counties.
#   2. tigris counties(year = 2021) instead of 2022: the 2022
#      file replaces Connecticut counties with planning regions,
#      which would drop Hartford County (09003) from the map.
#   3. Output paths point into this folder.
#   4. One added line after the spike indicator: her ifelse()
#      returns 0 (not NA) for the first-12-month burn-in rows,
#      but her comment and email both say those months should be
#      NA ("no spike value ... expected"). The added line sets
#      them to NA so n_months_eligible and the time series match
#      her stated intent. FLAGGED to her in the email.

library(dplyr)
library(zoo)      # for the rolling mean/sd
library(ggplot2)
library(sf)
library(tigris)   # county shapefiles

options(tigris_use_cache = TRUE)

setwd("C:/Users/xief/.local/bin/ucmerced/analysis/task1_spikes")

# ------------------------------------------------------------
# 0. Load county-month detention data (pre-built, zero-filled)
# ------------------------------------------------------------
df <- read.csv("detention_county_month.csv",
                colClasses = c(county_fips = "character"))

df$county_fips <- sprintf("%05d", as.numeric(df$county_fips))

df$date <- as.Date(paste(df$year, df$month, "01", sep = "-"))

# ------------------------------------------------------------
# 1. Define the enforcement-activity index E_{c,t}
# ------------------------------------------------------------
df$E <- df$detention_count

# ------------------------------------------------------------
# 2. Trailing 12-month mean and SD, by county
# ------------------------------------------------------------
df <- df %>%
  arrange(county_fips, date) %>%
  group_by(county_fips) %>%
  mutate(
    roll_mean = lag(rollapply(E, width = 12, FUN = mean, align = "right", fill = NA)),
    roll_sd   = lag(rollapply(E, width = 12, FUN = sd,   align = "right", fill = NA))
  ) %>%
  ungroup()

# ------------------------------------------------------------
# 3. Spike indicator
# ------------------------------------------------------------
df <- df %>%
  mutate(spike = ifelse(!is.na(roll_mean) & !is.na(roll_sd) &
                           E > roll_mean + 1.5 * roll_sd,
                         1, 0))

df$spike[is.na(df$roll_mean) | is.na(df$roll_sd)] <- NA

# ------------------------------------------------------------
# 4. County-level summary: frequency, duration, intensity
# ------------------------------------------------------------
county_summary <- df %>%
  group_by(county_fips) %>%
  summarise(
    n_months_eligible = sum(!is.na(spike)),
    n_spike_months    = sum(spike, na.rm = TRUE),
    spike_frequency   = n_spike_months / n_months_eligible,
    longest_streak = {
      r <- rle(spike[!is.na(spike)])
      if (any(r$values == 1)) max(r$lengths[r$values == 1]) else 0
    },
    intensity = mean(E[spike == 1], na.rm = TRUE) / mean(E[spike == 0], na.rm = TRUE)
  )

write.csv(county_summary, "table_spike_summary_by_county.csv", row.names = FALSE)

# ------------------------------------------------------------
# 5. National map
# ------------------------------------------------------------
us_counties <- counties(cb = TRUE, resolution = "20m", year = 2021) %>%
  select(GEOID, geometry)

map_data <- us_counties %>%
  left_join(county_summary, by = c("GEOID" = "county_fips"))

ggplot(map_data) +
  geom_sf(aes(fill = spike_frequency), color = NA) +
  scale_fill_viridis_c(name = "Spike\nfrequency", na.value = "grey90") +
  coord_sf(xlim = c(-125, -66), ylim = c(24, 50)) +
  theme_minimal() +
  labs(title = "Enforcement Spike Frequency by County",
       subtitle = "Share of eligible months flagged as a spike")

ggsave("fig1_national_spike_map.png", width = 10, height = 6, dpi = 300)

# ------------------------------------------------------------
# 6. Central Valley map
# ------------------------------------------------------------
# NOTE: this is HER 18-county list, unchanged. Verification of the
# "standard ~19-county definition" is being handled separately and
# flagged back to her (Solano 06095 is the usual 19th).
cv_fips <- c(
  "06007", # Butte
  "06011", # Colusa
  "06019", # Fresno
  "06021", # Glenn
  "06029", # Kern
  "06031", # Kings
  "06039", # Madera
  "06047", # Merced
  "06061", # Placer
  "06067", # Sacramento
  "06077", # San Joaquin
  "06089", # Shasta
  "06099", # Stanislaus
  "06101", # Sutter
  "06103", # Tehama
  "06107", # Tulare
  "06113", # Yolo
  "06115"  # Yuba
)

cv_map_data <- map_data %>% filter(GEOID %in% cv_fips)

ggplot(cv_map_data) +
  geom_sf(aes(fill = spike_frequency), color = "white") +
  scale_fill_viridis_c(name = "Spike\nfrequency") +
  theme_minimal() +
  labs(title = "Enforcement Spike Frequency: Central Valley Counties")

ggsave("fig1b_central_valley_spike_map.png", width = 8, height = 8, dpi = 300)

# ------------------------------------------------------------
# 7. Time series: national vs. Central Valley
# ------------------------------------------------------------
ts_national <- df %>%
  group_by(date) %>%
  summarise(share_counties_spiking = mean(spike, na.rm = TRUE)) %>%
  mutate(region = "National")

ts_cv <- df %>%
  filter(county_fips %in% cv_fips) %>%
  group_by(date) %>%
  summarise(share_counties_spiking = mean(spike, na.rm = TRUE)) %>%
  mutate(region = "Central Valley")

ts_combined <- bind_rows(ts_national, ts_cv)

ggplot(ts_combined, aes(x = date, y = share_counties_spiking, color = region)) +
  geom_line(linewidth = 1) +
  theme_minimal() +
  labs(title = "Share of Counties in an Enforcement Spike, Over Time",
       x = NULL, y = "Share of counties spiking", color = NULL)

ggsave("fig2_time_series.png", width = 9, height = 5, dpi = 300)

cat("DONE: table + 3 figures written to analysis/task1_spikes\n")
