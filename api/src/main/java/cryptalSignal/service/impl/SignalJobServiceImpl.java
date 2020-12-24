package cryptalSignal.service.impl;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import cryptalSignal.JobWorker.JobQueue;
import cryptalSignal.JobWorker.executor.CommandVersion;
import cryptalSignal.JobWorker.model.CryptalSingalParameter;
import cryptalSignal.JobWorker.model.Job;
import cryptalSignal.JobWorker.model.JobStatus;
import cryptalSignal.JobWorker.model.Parameters;

@Service
public class SignalJobServiceImpl {

    @Autowired
    private JobQueue jobQueue;


    public void submitCryptalSignal(String timeLevel, String exchangeId, List<String> coins) {
        //assemble param
        String signalJobType = "_write_strategic_data";
        Parameters parameters = new CryptalSingalParameter(timeLevel, exchangeId, signalJobType);
        //submit a job
        jobQueue.submit(new Job("app/apiHandler.py", CommandVersion.PYTHON3, parameters, JobStatus.RUNNING));
    }
}
