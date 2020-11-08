package cryptalSignal.JobWorker;

import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;

import org.springframework.stereotype.Component;

import cryptalSignal.JobWorker.model.Job;

@Component
public class JobQueue {
    private BlockingQueue<Job> jobQueue;
    private static final int NUMBER = 10;

    public JobQueue() {
        this.jobQueue = new ArrayBlockingQueue<>(NUMBER);
    }


    public boolean submit(Job job) {
        return this.jobQueue.offer(job);
    }


    public Job get() {
        return jobQueue.poll();
    }
}
