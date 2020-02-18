/**
 *
 **/
CREATE DATABASE acticloudDB;
USE acticloudDB;
CREATE TABLE hosts ( id int not null unique auto_increment,
                     name varchar(50),
                     nr_pcpus smallint unsigned,
                     ram_gb int unsigned,
                     is_lab tinyint unsigned );
CREATE TABLE vms ( id varchar(50) not null unique,
                   hostname varchar(50),
                   nr_vcpus smallint unsigned,
                   no_migrations int unsigned,
                   no_moves int unsigned,
                   is_gold tinyint unsigned,
                   is_noisy tinyint unsigned,
                   is_sensitive tinyint unsigned,
                   cost_function tinyint unsigned );
CREATE TABLE healthy_state_models ( bench_name varchar(50),
                                    nr_vcpus smallint unsigned,
                                    model longblob );
/* 'unit' can be one of "throughput" or "time" */
CREATE TABLE bench_isolation_performance ( bench_name varchar(50),
                                           nr_vcpus smallint unsigned,
                                           performance float signed,
                                           unit varchar(20) );
CREATE TABLE bench_isolation_perf_metrics ( bench_name varchar(50),
                                            nr_vcpus smallint unsigned,
                                            time datetime,
                                            metric varchar(50),
                                            value float signed )
CREATE TABLE vm_heartbeats ( id varchar(50) not null,
                             time datetime,
                             performance float signed,
                             base_performance float signed,
                             slowdown float signed,
                             hostname varchar(50) );
CREATE TABLE external_profit_reports ( hostname varchar(50),
                                       time datetime,
                                       id varchar(50) not null,
                                       profit_before float signed,
                                       profit_after float signed,
                                       profit_diff float signed );
CREATE TABLE internal_profit_reports ( hostname varchar(50),
                                       time datetime,
                                       profit float signed );
