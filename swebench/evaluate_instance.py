import base64
import json
import logging
import os
import sys

from swebench.constants import PatchType, KEY_PREDICTION
from swebench.context_manager import TaskEnvContextManager
from swebench.utils import extract_minimal_patch


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger("evaluate_instance")


def main(
    task_instance: dict,
    testbed_name: str,
    testbed: str,
    log_dir: str,
    timeout: int,
    log_suffix: str = None
):
    logger.info(f"Instance ID: {task_instance['instance_id']}\n"
                f"Testbed: {testbed_name}\n"
                f"Log dir: {log_dir}")

    with TaskEnvContextManager(
            task_instance,
            testbed_name,
            testbed,
            log_dir,
            timeout=timeout,
            log_suffix=log_suffix,
    ) as tcm:

        # Attempt to apply prediction
        patch_type = PatchType.PATCH_PRED_TRY.value

        # If prediction patch doesn't apply, try to do some minor patch refactoring and try again
        if not tcm.apply_patch(task_instance[KEY_PREDICTION], patch_type=patch_type) \
                and task_instance[KEY_PREDICTION] is not None \
                and task_instance[KEY_PREDICTION] != "":
            task_instance[KEY_PREDICTION] = extract_minimal_patch(task_instance[KEY_PREDICTION])
            patch_type = PatchType.PATCH_PRED_MINIMAL_TRY.value
            if not tcm.apply_patch(task_instance[KEY_PREDICTION], patch_type=patch_type):
                logger.warning("Failed to apply prediction patch")
                sys.exit(1)

        tcm.apply_patch(task_instance[KEY_PREDICTION], patch_type=patch_type, revert=True)

        # Set prediction patch label based on whether patch was edited
        if patch_type == PatchType.PATCH_PRED_MINIMAL_TRY.value:
            patch_type = PatchType.PATCH_PRED_MINIMAL.value
        else:
            patch_type = PatchType.PATCH_PRED.value

        # Run testing script
        if (
                not tcm.apply_patch(task_instance[KEY_PREDICTION], patch_type=patch_type)
                or not tcm.apply_patch(task_instance["test_patch"], patch_type=PatchType.PATCH_TEST.value)
                or not tcm.run_tests_task(task_instance)
        ):
            logger.warning("Evaluation failed")
            sys.exit(1)

        logger.info("Evaluation succeeded")


if __name__ == "__main__":
    assert os.getenv('INSTANCE') is not None, "INSTANCE environment variable is not set"
    assert os.getenv('LOG_DIR') is not None, "LOG_DIR environment variable is not set"
    assert os.getenv('TESTBED') is not None, "TESTBED environment variable is not set"
    assert os.getenv('TESTBED_NAME') is not None, "TESTBED_NAME environment variable is not set"

    task_instance = json.loads(base64.b64decode(os.getenv('INSTANCE')).decode('utf-8'))

    main(
        task_instance=task_instance,
        testbed_name=os.getenv('TESTBED_NAME'),
        testbed=os.getenv('TESTBED'),
        log_dir=os.getenv('LOG_DIR'),
        timeout=int(os.getenv('TIMEOUT')) if os.getenv('TIMEOUT') is not None else None,
        log_suffix=os.getenv('LOG_SUFFIX')
    )
