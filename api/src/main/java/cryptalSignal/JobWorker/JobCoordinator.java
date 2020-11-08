package cryptalSignal.JobWorker;

import static java.util.concurrent.Executors.newFixedThreadPool;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Semaphore;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.ApplicationContext;

import cryptalSignal.JobWorker.executor.JobExecutor;
import cryptalSignal.JobWorker.model.Job;
import cryptalSignal.JobWorker.model.JobStatus;

public class JobCoordinator {

    private final Logger logger = LoggerFactory.getLogger(this.getClass());
    private Semaphore tokens;
    private ExecutorService JobPool;
    private JobQueue jobQueue;
    private Class<? extends JobExecutor> type;
    private ApplicationContext applicationContext;

    private static final int WORKER_POOL_NUMBER = 4;

    public JobCoordinator(JobQueue jobQueue, Class<? extends JobExecutor> type, ApplicationContext applicationContext) {
        this.tokens = new Semaphore(WORKER_POOL_NUMBER);
        this.JobPool = newFixedThreadPool(WORKER_POOL_NUMBER);
        this.jobQueue = jobQueue;
        this.type = type;
        this.applicationContext = applicationContext;
    }

    public void start() {
        while(!Thread.interrupted()) {
            try {
                tokens.acquire();

                Job job = jobQueue.get();
                if(job == null) {
                    tokens.release();
                    Thread.sleep(2000);
                } else {
                    logger.info("get one task. submitting...");
                    final JobExecutor jobExecutor = applicationContext.getBean(type);
                    //launch a job
                    job.setStatus(JobStatus.SUBMITTED);
                    JobPool.submit(new JobRunner(job, jobExecutor, tokens));
                    logger.info("task submitted...");
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                tokens.release();
            } catch (Exception e) {
                tokens.release();
            }
        }
    }


    public void stop() {
        JobPool.shutdown();
    }

}
