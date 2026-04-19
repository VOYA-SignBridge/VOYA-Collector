import axiosClient from "./axiosClient";
import { validateJobStatus } from "./validators";
import type { Result } from "./validators";
import type { JobStatus } from "../types";

export const getJobStatus = async (jobId: string): Promise<Result<JobStatus>> => {
  const res = await axiosClient.get(`/jobs/${jobId}`);
  return validateJobStatus(res.data);
};
