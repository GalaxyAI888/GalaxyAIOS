# -*- coding: utf-8 -*-
import argparse
import asyncio
import logging
import multiprocessing
import os
from typing import Optional, Dict, Any

import yaml

from aistack.log import setup_logging
from aistack.config.config import Config, set_global_config
from aistack.server.server import Server
from aistack.worker.worker import Worker

LOG = logging.getLogger(__name__)



class OptionalBoolAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(OptionalBoolAction, self).__init__(
            option_strings, dest, nargs=0, **kwargs
        )
        self.default = None

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, True)


def setup_start_cmd(parsers: argparse.ArgumentParser):
    # parser_server: argparse.ArgumentParser = subparsers.add_parser(
    #     "start",
    #     help="Run GPUStack server or worker.",
    #     description="Run GPUStack server or worker.",
    # )
    parser_server = parsers
    group = parser_server.add_argument_group("Common settings")
    group.add_argument(
        "--config-file",
        type=str,
        help="Path to the YAML config file.",
        default=get_aistack_env("CONFIG_FILE"),
    )
    group.add_argument(
        "-d",
        "--debug",
        action=OptionalBoolAction,
        help="Enable debug mode.",
        default=True,
    )
    group.add_argument(
        "--data-dir",
        type=str,
        help="Directory to store data. Default is OS specific.",
        default=get_aistack_env("DATA_DIR"),
    )
    group.add_argument(
        "--cache-dir",
        type=str,
        help="Directory to store cache (e.g., model files). Defaults to <data-dir>/cache.",
        default=get_aistack_env("CACHE_DIR"),
    )
    group.add_argument(
        "--bin-dir",
        type=str,
        help="Directory to store additional binaries, e.g., versioned backend executables.",
        default=get_aistack_env("BIN_DIR"),
    )

    group = parser_server.add_argument_group("Server settings")
    group.add_argument(
        "--host",
        type=str,
        help="Host to bind the server to.",
        default="0.0.0.0",
    )
    group.add_argument(
        "--port",
        type=int,
        help="Port to bind the server to.",
        default=9999
    )
    group.add_argument(
        "--database-url",
        type=str,
        help="URL of the database. Example: postgresql://user:password@hostname:port/db_name.",
        default=get_aistack_env("DATABASE_URL"),
    )
    group.add_argument(
        "--bootstrap-password",
        type=str,
        help="Initial password for the default admin user. Random by default.",
        default="123456"
    )
    group.add_argument(
        "--ssl-keyfile",
        type=str,
        help="Path to the SSL key file.",
        default=get_aistack_env("SSL_KEYFILE"),
    )
    group.add_argument(
        "--ssl-certfile",
        type=str,
        help="Path to the SSL certificate file.",
        default=get_aistack_env("SSL_CERTFILE"),
    )
    group.add_argument(
        "--force-auth-localhost",
        action=OptionalBoolAction,
        help="Force authentication for requests originating from localhost (127.0.0.1)."
        "When set to True, all requests from localhost will require authentication.",
        default=get_aistack_env_bool("FORCE_AUTH_LOCALHOST"),
    )

    parser_server.set_defaults(func=run)


def load_config_from_yaml(yaml_file: str) -> Dict[str, Any]:
    with open(yaml_file, "r") as file:
        return yaml.safe_load(file)


def set_config_option(args, config_data: dict, option_name: str):
    option_value = getattr(args, option_name, None)
    if option_value is not None:
        config_data[option_name] = option_value


def set_common_options(args, config_data: dict):
    options = [
        "debug",
        "data_dir",
        "cache_dir",
        "bin_dir",
        "pipx_path",
        "token",
        "huggingface_token",
    ]

    for option in options:
        set_config_option(args, config_data, option)


def set_server_options(args, config_data: dict):
    options = [
        "host",
        "port",
        "database_url",
        "disable_worker",
        "bootstrap_password",
        "ssl_keyfile",
        "ssl_certfile",
        "force_auth_localhost",
        "ollama_library_base_url",
        "disable_update_check",
        "update_check_url",
    ]

    for option in options:
        set_config_option(args, config_data, option)


def set_worker_options(args, config_data: dict):
    options = [
        "server_url",
        "worker_ip",
        "worker_name",
        "worker_port",
        "disable_metrics",
        "disable_rpc_servers",
        "metrics_port",
        "log_dir",
        "system_reserved",
        "tools_download_base_url",
    ]

    for option in options:
        set_config_option(args, config_data, option)


def parse_args(args: argparse.Namespace) -> Config:
    config_data = {}
    if args.config_file:
        config_data.update(load_config_from_yaml(args.config_file))

    # CLI args have higher priority than config file
    set_common_options(args, config_data)
    set_server_options(args, config_data)
    set_worker_options(args, config_data)

    cfg = Config(**config_data)
    set_global_config(cfg)
    return cfg


def run(args: argparse.Namespace):
    try:
        cfg = parse_args(args)
        setup_logging(cfg.debug)
        multiprocessing.set_start_method('spawn')
        LOG.info("Starting AIStack")
        run_server(cfg)
    except Exception as e:
        print(f"Failed to start: {e}")
        LOG.fatal(e)


def run_server(cfg: Config):
    sub_processes = []

    if not cfg.disable_worker:
        # Start the worker
        worker = Worker(cfg)
        worker_process = multiprocessing.Process(target=worker.start)
        sub_processes.append(worker_process)

    # Start the server
    server = Server(cfg, sub_processes)
    try:
        asyncio.run(server.start())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    except  Exception as e:
        LOG.error(f"Failed to start server: {e}")
    finally:
        LOG.info("server has shutdown")


def get_aistack_env(env_var: str) -> Optional[str]:
    env_name = "AISTACK_" + env_var
    return os.getenv(env_name)


def get_aistack_env_bool(env_var: str) -> Optional[bool]:
    env_name = "AISTACK_" + env_var
    env_value = os.getenv(env_name)
    if env_value is not None:
        return env_value.lower() in ["true", "True"]
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Aistack",
        conflict_handler="resolve",
        add_help=True,
        formatter_class=lambda prog: argparse.HelpFormatter(
            prog, max_help_position=55, indent_increment=2, width=200
        ),
    )
    # subparsers = parser.add_subparsers(
    #     help="sub-command help", metavar='{start}'
    # )

    setup_start_cmd(parser)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        run(args)
