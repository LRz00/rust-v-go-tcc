use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use chrono::{NaiveDate, Utc};
use deadpool_postgres::{Config, Pool, PoolConfig};
use serde::Serialize;
use std::env;
use std::fs;
use std::hint::black_box;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio_postgres::NoTls;

#[derive(Serialize)]
struct Resp {
    days_since: i64,
}

async fn days_since(pool: web::Data<Pool>) -> impl Responder {
    let client = match pool.get().await {
        Ok(c) => c,
        Err(_) => return HttpResponse::InternalServerError().body("pool error"),
    };

    // Pegamos como String para evitar problemas de trait FromSql
    let row = match client
        .query_one(
            "SELECT reference_date::TEXT FROM base_date WHERE id = 1",
            &[],
        )
        .await
    {
        Ok(r) => r,
        Err(_) => return HttpResponse::InternalServerError().body("query error"),
    };

    let date_str: String = row.get(0);

    let date = match NaiveDate::parse_from_str(&date_str, "%Y-%m-%d") {
        Ok(d) => d,
        Err(_) => return HttpResponse::InternalServerError().body("date parse error"),
    };

    let today = Utc::now().date_naive();
    let days = (today - date).num_days();

    HttpResponse::Ok().json(Resp { days_since: days })
}

#[derive(Serialize)]
struct HeavyResp {
    days_since: i64,
    checksum: usize,
}

async fn days_since_heavy(pool: web::Data<Pool>) -> impl Responder {
    // Workload sintético de alocação
    // Aloca 1MB de dados temporários
    const ALLOC_SIZE: usize = 1 * 1024 * 1024; // 1MB
    let mut buffer = vec![0u8; ALLOC_SIZE];
    let seed = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos() as usize;

    // Preenche o buffer para forçar alocação real
    for i in (0..buffer.len()).step_by(4096) {
        buffer[i] = ((i + seed) % 256) as u8;
    }

    // Faz algum processamento para evitar otimização do compilador
    let sum: usize = buffer.iter().step_by(1024).map(|&x| x as usize).sum();

    // Continua com a lógica normal
    let client = match pool.get().await {
        Ok(c) => c,
        Err(_) => return HttpResponse::InternalServerError().body("pool error"),
    };

    let row = match client
        .query_one(
            "SELECT reference_date::TEXT FROM base_date WHERE id = 1",
            &[],
        )
        .await
    {
        Ok(r) => r,
        Err(_) => return HttpResponse::InternalServerError().body("query error"),
    };

    let date_str: String = row.get(0);

    let date = match NaiveDate::parse_from_str(&date_str, "%Y-%m-%d") {
        Ok(d) => d,
        Err(_) => return HttpResponse::InternalServerError().body("date parse error"),
    };

    let today = Utc::now().date_naive();
    let days = (today - date).num_days();

    black_box(&buffer);

    HttpResponse::Ok().json(HeavyResp {
        days_since: days,
        checksum: sum, // Previne otimização
    })
}

#[derive(Serialize)]
struct MetricsResponse {
    timestamp: String,
    rss_bytes: u64,
    vsz_bytes: u64,
    rss_mb: f64,
    vsz_mb: f64,
}

fn read_proc_stat() -> Result<MetricsResponse, String> {
    // Lê /proc/self/statm para obter informações de memória
    // Formato: size resident shared text lib data dt
    // size = tamanho do programa virtual (VSZ)
    // resident = tamanho residente (RSS)
    let statm = fs::read_to_string("/proc/self/statm")
        .map_err(|e| format!("failed to read statm: {}", e))?;

    let parts: Vec<&str> = statm.split_whitespace().collect();
    if parts.len() < 2 {
        return Err("invalid statm format".to_string());
    }

    // Páginas de memória (normalmente 4096 bytes)
    let page_size: u64 = 4096;

    let vsz_pages: u64 = parts[0].parse().map_err(|e| format!("parse vsz: {}", e))?;
    let rss_pages: u64 = parts[1].parse().map_err(|e| format!("parse rss: {}", e))?;

    let vsz_bytes = vsz_pages * page_size;
    let rss_bytes = rss_pages * page_size;

    let rss_mb = rss_bytes as f64 / (1024.0 * 1024.0);
    let vsz_mb = vsz_bytes as f64 / (1024.0 * 1024.0);

    Ok(MetricsResponse {
        timestamp: chrono::Utc::now().to_rfc3339(),
        rss_bytes,
        vsz_bytes,
        rss_mb,
        vsz_mb,
    })
}

#[derive(Debug, Default)]
struct MemStatusVM {
    vm_rss_kb: u64, // RSS atual em KB
    vm_hwm_kb: u64, // Pico de RSS em KB
}

fn read_proc_self_status() -> Result<MemStatusVM, String> {
    let content = fs::read_to_string("/proc/self/status")
        .map_err(|e| format!("failed to read /proc/self/status: {}", e))?;

    let mut result = MemStatusVM::default();

    for line in content.lines() {
        if let Some(rest) = line.strip_prefix("VmRSS:") {
            if let Some(val) = parse_status_kb_line(rest) {
                result.vm_rss_kb = val;
            }
        } else if let Some(rest) = line.strip_prefix("VmHWM:") {
            if let Some(val) = parse_status_kb_line(rest) {
                result.vm_hwm_kb = val;
            }
        }
    }

    Ok(result)
}

fn parse_status_kb_line(rest: &str) -> Option<u64> {
    rest.split_whitespace().next()?.parse::<u64>().ok()
}

#[derive(Debug, Default)]
struct CgroupMemStats {
    version: String, // "v1" ou "v2" or "unknown"
    current_bytes: u64,
    peak_bytes: u64,
    max_bytes: u64,
    unlimited: bool,
}
fn read_cgroup_mem_stats() -> Result<CgroupMemStats, String> {
    if let Ok(stats) = read_cgroup_v2() {
        return Ok(stats);
    }

    if let Ok(stats) = read_cgroup_v1() {
        return Ok(stats);
    }

    Err("neither cgroup v2 nor v1 memory files are readable".to_string())
}

fn read_cgroup_v2() -> Result<CgroupMemStats, String> {
    let current = read_cgroup_uint_file("/sys/fs/cgroup/memory.current")?;

    //memory peak might no exist in older kernels, failing the whole read is not ideal
    let peak = read_cgroup_uint_file("/sys/fs/cgroup/memory.peak").unwrap_or(0);

    let max_raw = fs::read_to_string("/sys/fs/cgroup/memory.max")
        .map_err(|e| format!("Failed to read memory.max: {}", e))?;

    let max_str = max_raw.trim();

    let (maxx_bytes, unlimited) = if max_str == "max" {
        (0, true)
    } else {
        let val = max_str
            .parse::<u64>()
            .map_err(|e| format!("failed to parse memory.max: {}", e))?;
        (val, false)
    };

    Ok(CgroupMemStats {
        version: "v2".into(),
        current_bytes: current,
        peak_bytes: peak,
        max_bytes: maxx_bytes,
        unlimited,
    })
}

fn read_cgroup_v1() -> Result<CgroupMemStats, String> {
    let current = read_cgroup_uint_file("/sys/fs/cgroup/memory/memory.usage_in_bytes")?;
    let peak = read_cgroup_uint_file("/sys/fs/cgroup/memory/memory.max_usage_in_bytes")?;
    let max = read_cgroup_uint_file("/sys/fs/cgroup/memory/memory.limit_in_bytes")?;

    const V1_UNLIMITED: u64 = 1u64 << 62;
    let unlimited = max >= V1_UNLIMITED;

    Ok(CgroupMemStats {
        version: "v1".into(),
        current_bytes: current,
        peak_bytes: peak,
        max_bytes: max,
        unlimited,
    })
}

fn read_cgroup_uint_file(path: &str) -> Result<u64, String> {
    let content =
        fs::read_to_string(path).map_err(|e| format!("failed to read {}: {}", path, e))?;
    content
        .trim()
        .parse::<u64>()
        .map_err(|e| format!("failed to parse {}: {}", path, e))
}

async fn metrics() -> impl Responder {
    match read_proc_stat() {
        Ok(m) => HttpResponse::Ok().json(m),
        Err(e) => HttpResponse::InternalServerError().body(e),
    }
}

async fn health() -> impl Responder {
    HttpResponse::Ok().body("OK")
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // Lê variáveis do docker-compose
    let db_host = env::var("POSTGRES_HOST").unwrap_or("postgres".into());
    let db_user = env::var("POSTGRES_USER").unwrap_or("tcc".into());
    let db_pass = env::var("POSTGRES_PASSWORD").unwrap_or("tcc".into());
    let db_name = env::var("POSTGRES_DB").unwrap_or("tcc".into());

    let mut cfg = Config::new();
    cfg.host = Some(db_host);
    cfg.user = Some(db_user);
    cfg.password = Some(db_pass);
    cfg.dbname = Some(db_name);
    cfg.pool = Some(PoolConfig {
        max_size: 25,
        ..Default::default()
    });

    let pool = cfg.create_pool(NoTls).unwrap();

    println!("Rust API listening on 0.0.0.0:8080");

    match read_proc_self_status() {
        Ok(status) => println!(
            "VmRSS: {} KB, VmHWM: {} KB",
            status.vm_rss_kb, status.vm_hwm_kb
        ),
        Err(e) => println!("Error reading /proc/self/status: {}", e),
    }

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(pool.clone()))
            .route("/days-since", web::get().to(days_since))
            .route("/days-since-heavy", web::get().to(days_since_heavy))
            .route("/metrics", web::get().to(metrics))
            .route("/health", web::get().to(health))
    })
    .bind(("0.0.0.0", 8080))?
    .run()
    .await
}
