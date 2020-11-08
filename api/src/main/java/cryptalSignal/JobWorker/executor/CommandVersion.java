package cryptalSignal.JobWorker.executor;

public enum CommandVersion {

    PYTHON3("/usr/local/bin/python3"),
    PYTHON("/usr/bin/python");

    private String commandPath;

    CommandVersion(String commandPath) {
        this.commandPath = commandPath;
    }

    public String getCommandPath() {
        return commandPath;
    }
}
