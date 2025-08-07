import csv
import logging
import subprocess
from aistack.detectors.base import GPUDetector
from aistack.schemas.workers import (
    GPUCoreInfo,
    GPUDeviceInfo,
    GPUDevicesInfo,
    MemoryInfo,
    VendorEnum,
)
from aistack.utils import platform
from aistack.utils.command import is_command_available
from aistack.utils.convert import safe_float, safe_int

logger = logging.getLogger(__name__)


class NvidiaSMI(GPUDetector):
    def is_available(self) -> bool:
        logger.info("Checking if nvidia-smi is available...")
        available = is_command_available("nvidia-smi")
        logger.info(f"nvidia-smi available: {available}")
        return available

    def gather_gpu_info(self) -> GPUDevicesInfo:
        logger.info("Starting GPU info gathering with nvidia-smi...")
        command = self._command_gather_gpu()
        results = self._run_command(command)
        if results is None:
            logger.warning("nvidia-smi returned no results")
            return []

        logger.info("nvidia-smi command executed successfully, decoding results...")
        devices = self.decode_gpu_devices(results)
        logger.info(f"Decoded {len(devices)} GPU devices from nvidia-smi")
        return devices

    def decode_gpu_devices(self, result) -> GPUDevicesInfo:  # noqa: C901
        """
        results example:
        $nvidia-smi --format=csv,noheader --query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu
        0, NVIDIA GeForce RTX 4080 SUPER, 16376 MiB, 1309 MiB, 0 %, 41
        1, NVIDIA GeForce RTX 4080 SUPER, 16376 MiB, 13625 MiB, 0 %, 39
        """
        logger.info(f"Decoding GPU devices from nvidia-smi output: {len(result.splitlines())} lines")
        logger.info(f"Raw nvidia-smi output: {result}")

        devices = []
        reader = csv.reader(result.splitlines())
        for i, row in enumerate(reader):
            logger.info(f"Processing nvidia-smi row {i}: {row}")
            if len(row) < 6:
                logger.warning(f"Row {i} has insufficient columns ({len(row)} < 6), skipping")
                continue
            index, name, memory_total, memory_used, utilization_gpu, temperature_gpu = (
                row
            )

            index = safe_int(index)
            name = name.strip()
            # Convert MiB to bytes
            memory_total = safe_int(memory_total.split()[0]) * 1024 * 1024
            # Convert MiB to bytes
            memory_used = safe_int(memory_used.split()[0]) * 1024 * 1024
            utilization_gpu = safe_float(
                utilization_gpu.split()[0]
            )  # Remove the '%' sign
            temperature_gpu = safe_float(temperature_gpu)

            device = GPUDeviceInfo(
                index=index,
                device_index=index,
                device_chip_index=0,
                name=name,
                vendor=VendorEnum.NVIDIA.value,
                memory=MemoryInfo(
                    is_unified_memory=False,
                    used=memory_used,
                    total=memory_total,
                    utilization_rate=(
                        (memory_used / memory_total) * 100 if memory_total > 0 else 0
                    ),
                ),
                core=GPUCoreInfo(
                    utilization_rate=utilization_gpu,
                    total=0,  # Total cores information is not provided by nvidia-smi
                ),
                temperature=temperature_gpu,
                type=platform.DeviceTypeEnum.CUDA.value,
            )
            devices.append(device)
            logger.info(f"Added GPU device: {name} (index: {index}, memory: {memory_total//(1024*1024)}MB, temp: {temperature_gpu}°C, utilization: {utilization_gpu}%)")
        
        logger.info(f"GPU decoding completed, found {len(devices)} valid GPU devices")
        return devices

    def _run_command(self, command):
        logger.info(f"Executing nvidia-smi command: {' '.join(command)}")
        result = None
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8"
            )

            logger.info(f"Command executed successfully, return code: {result.returncode}")
            if result.stdout:
                logger.info(f"Command stdout (full): {result.stdout}")
            if result.stderr:
                logger.info(f"Command stderr (full): {result.stderr}")

            if result is None or result.stdout is None:
                logger.error("Command returned None or empty stdout")
                return None

            output = result.stdout
            if "no devices" in output.lower():
                logger.warning("nvidia-smi reported no devices")
                return None

            if result.returncode != 0:
                logger.error(f"Command failed with return code: {result.returncode}")
                raise Exception(f"Unexpected return code: {result.returncode}")

            if output == "" or output is None:
                logger.error("Command output is empty")
                raise Exception(f"Output is empty, return code: {result.returncode}")

            logger.info("nvidia-smi command completed successfully")
            return output
        except Exception as e:
            error_message = f"Failed to execute {command}: {e}"
            if result:
                logger.error(f"Command failed with return code: {result.returncode}")
                logger.error(f"Failed command stdout: {result.stdout}")
                logger.error(f"Failed command stderr: {result.stderr}")
                error_message += f", stdout: {result.stdout}, stderr: {result.stderr}"
            else:
                logger.error("Command failed before execution (no result object)")
            logger.error(error_message)
            raise Exception(error_message)

    def _command_gather_gpu(self):
        executable_command = [
            "nvidia-smi",
            "--format=csv,noheader",
            "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu",
        ]
        logger.info(f"Generated nvidia-smi command: {executable_command}")
        return executable_command
