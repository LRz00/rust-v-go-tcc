use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use chrono::{NaiveDate, Utc};
use deadpool_postgres::{Config, Pool};
use serde::Serialize;
use tokio_postgres::NoTls;
use std::env;

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
        .query_one("SELECT reference_date::TEXT FROM base_date WHERE id = 1", &[])
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

    let pool = cfg.create_pool(NoTls).unwrap();

    println!("Rust API listening on 0.0.0.0:8080");

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(pool.clone()))
            .route("/days-since", web::get().to(days_since))
    })
    .bind(("0.0.0.0", 8080))?
    .run()
    .await
}
