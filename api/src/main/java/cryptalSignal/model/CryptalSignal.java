package cryptalSignal.model;

import java.util.List;

import org.springframework.web.bind.annotation.ResponseBody;

import cryptalSignal.JobWorker.model.JobStatus;

@ResponseBody
public class CryptalSignal {
    private String id;
    private JobStatus status;
    private List<CryptalSignalObject> cryptalSignals;

    public CryptalSignal(String id, JobStatus status, List<CryptalSignalObject> cryptalSignals) {
        this.id = id;
        this.status = status;
        this.cryptalSignals = cryptalSignals;
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public JobStatus getStatus() {
        return status;
    }

    public void setStatus(JobStatus status) {
        this.status = status;
    }

    public List<CryptalSignalObject> getCryptalSignals() {
        return cryptalSignals;
    }

    public void setCryptalSignals(List<CryptalSignalObject> cryptalSignals) {
        this.cryptalSignals = cryptalSignals;
    }
}
