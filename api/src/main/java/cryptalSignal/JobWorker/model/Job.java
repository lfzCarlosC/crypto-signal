package cryptalSignal.JobWorker.model;

import cryptalSignal.JobWorker.executor.CommandVersion;

public class Job {

    private String id;
    private String commandHeader;
    private CommandVersion commandVersion;
    private Parameters parameters;
    private JobStatus status;

    public Job(String commandHeader, CommandVersion commandVersion, Parameters parameters, JobStatus status) {
        this.commandHeader = commandHeader;
        this.commandVersion = commandVersion;
        this.parameters = parameters;
        this.status = status;
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getCommandHeader() {
        return commandHeader;
    }

    public void setCommandHeader(String commandHeader) {
        this.commandHeader = commandHeader;
    }

    public CommandVersion getCommandVersion() {
        return commandVersion;
    }

    public void setCommandVersion(CommandVersion commandVersion) {
        this.commandVersion = commandVersion;
    }

    public Parameters getParameters() {
        return parameters;
    }

    public void setParameters(Parameters parameters) {
        this.parameters = parameters;
    }

    public JobStatus getStatus() {
        return status;
    }

    public void setStatus(JobStatus status) {
        this.status = status;
    }
}
