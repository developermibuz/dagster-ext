import json
import logging
import os
import subprocess
from functools import lru_cache
from typing import Dict, List, Optional

from dagster import In, Nothing, get_dagster_logger, job, op, resource

from dagster_meltano.job import Job
from dagster_meltano.meltano_invoker import MeltanoInvoker
from dagster_meltano.schedule import Schedule
from dagster_meltano.utils import Singleton, generate_dagster_name

logger = get_dagster_logger()


class MeltanoResource(metaclass=Singleton):
    def __init__(self, project_dir: str = None, meltano_bin: Optional[str] = "meltano"):
        self.project_dir = project_dir
        self.meltano_bin = meltano_bin
        self.meltano_invoker = MeltanoInvoker(
            meltano_bin,
            log_level="info",  # TODO: Get this from the resource config
        )

    # TODO: Refactor to different file
    def run_cli(self, commands: List[str]):
        return json.loads(
            subprocess.run(
                [self.meltano_bin] + commands,
                cwd=self.project_dir or os.getcwd(),
                stdout=subprocess.PIPE,
                universal_newlines=True,
                check=True,
            ).stdout
        )

    @property
    @lru_cache
    def meltano_jobs(self) -> List[Job]:
        meltano_job_list = self.run_cli(["job", "list", "--format=json"])
        meltano_job_list = meltano_job_list["jobs"]
        return [Job(meltano_job, self.meltano_invoker) for meltano_job in meltano_job_list]

    @property
    @lru_cache
    def meltano_schedules(self) -> List[Schedule]:
        meltano_schedule_list = self.run_cli(["schedule", "list", "--format=json"])
        meltano_schedule_list = meltano_schedule_list["schedules"]["job"]
        schedule_list = [Schedule(meltano_schedule) for meltano_schedule in meltano_schedule_list]
        return schedule_list

    @property
    def meltano_job_schedules(self) -> Dict[str, Schedule]:
        return {schedule.job_name: schedule for schedule in self.meltano_schedules}

    @property
    def jobs(self) -> List[dict]:
        for meltano_job in self.meltano_jobs:
            yield meltano_job.dagster_job

            if meltano_job.name in self.meltano_job_schedules:
                yield self.meltano_job_schedules[meltano_job.name].dagster_schedule


@resource(description="A resource that corresponds to a Meltano project.")
def meltano_resource(init_context):
    # project_dir = init_context.resource_config["project_dir"]
    # return MeltanoResource(project_dir)
    return MeltanoResource()


if __name__ == "__main__":
    meltano_resource = MeltanoResource("/workspace/meltano")
    print(meltano_resource)
