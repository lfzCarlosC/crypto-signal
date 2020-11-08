package cryptalSignal.JobWorker;

import java.util.concurrent.Semaphore;

import cryptalSignal.JobWorker.executor.JobExecutor;
import cryptalSignal.JobWorker.model.Job;

public class JobRunner implements Runnable {

    private Job job;
    private JobExecutor jobExecutor;
    private Semaphore tokens;

    public JobRunner(Job job, JobExecutor jobExecutor, Semaphore tokens) {
        this.job = job;
        this.jobExecutor = jobExecutor;
        this.tokens = tokens;
    }

    @Override
    public void run() {
        String response = jobExecutor.execute(job);
        System.out.println(response);
        tokens.release();
    }
}
