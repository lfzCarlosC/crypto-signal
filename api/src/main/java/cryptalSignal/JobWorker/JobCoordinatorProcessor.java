package cryptalSignal.JobWorker;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import org.springframework.beans.BeansException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.ApplicationContext;
import org.springframework.context.ApplicationContextAware;
import org.springframework.context.SmartLifecycle;
import org.springframework.stereotype.Component;

import cryptalSignal.JobWorker.executor.JobExecutor;

@Component
public class JobCoordinatorProcessor implements SmartLifecycle, ApplicationContextAware {

    private List<JobCoordinator> jobCoordinators;
    private boolean isRunning = false;
    private JobQueue jobJobQueue;

    @Autowired
    public JobCoordinatorProcessor(JobQueue jobJobQueue) {
        this.jobJobQueue = jobJobQueue;
    }

    public boolean isAutoStartup() {
        return true;
    }

    @Override
    public void stop(Runnable runnable) {
        jobCoordinators.forEach(JobCoordinator::stop);
        isRunning = false;

    }

    public void start() {
        jobCoordinators.forEach(jobCoordinator -> {
            new Thread(()-> jobCoordinator.start()).start();
        });
        isRunning = true;
    }

    public void stop() {
        jobCoordinators.forEach(JobCoordinator::stop);
        isRunning = false;
    }

    public boolean isRunning() {
        return isRunning;
    }

    public int getPhase() {
        return 0;
    }

    public void setApplicationContext(ApplicationContext applicationContext) throws BeansException {
        jobCoordinators = new ArrayList<>();
        String[] names = applicationContext.getBeanNamesForType(JobExecutor.class);
        Arrays.stream(names).forEach(name -> {
            Class<? extends JobExecutor> type = (Class<? extends JobExecutor>) applicationContext.getAutowireCapableBeanFactory().getType(name);
            jobCoordinators.add(new JobCoordinator(jobJobQueue, type, applicationContext));
        });

    }
}
