package cryptalSignal.JobWorker.executor;

import cryptalSignal.JobWorker.model.Job;

public interface JobExecutor {
    public String execute(Job job);
}
