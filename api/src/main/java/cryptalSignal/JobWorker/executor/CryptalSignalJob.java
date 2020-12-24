package cryptalSignal.JobWorker.executor;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.util.Map;

import org.springframework.stereotype.Component;

import cryptalSignal.JobWorker.model.Job;

@Component
public class CryptalSignalJob implements JobExecutor{

    private String baseDir = System.getProperty("user.dir");
    private static final String SPACE = " ";

    @Override
    public String execute(Job job) {
        CommandVersion pythonCommand = job.getCommandVersion();
        Map<String, String> params = job.getParameters().getParams();
        String timeLevel = params.get("timeLevel");
        String exchangeId = params.get("exchangeId");
        String signalJobType =  params.get("signalJobType");
        String commandParams = generateExecuteString(timeLevel, exchangeId, signalJobType);
       try {
           File workingDir = new File(baseDir + "/..");
           Process process2 = Runtime.getRuntime().exec(pythonCommand.getCommandPath() + SPACE + baseDir + "/../" + job.getCommandHeader() + SPACE + commandParams, null, workingDir);

           BufferedReader infoReader = new BufferedReader(new InputStreamReader(process2.getInputStream()));
           infoReader.lines().forEach(System.out::println);

           String fileId = baseDir + "/../tmp/" + exchangeId + "-" + timeLevel + "-" + signalJobType;return getResponse(fileId);
        } catch (IOException e) {
           throw new RuntimeException(e);
       }

    }

    private String generateExecuteString(String timeLevel, String exchangeId, String signalJobType) {
        StringBuilder stringBuilder = new StringBuilder();
        String exchangeWithTimeLevel = exchangeId + "_" + timeLevel;
        stringBuilder.append("custom/" + exchangeWithTimeLevel +"_custom.yml" + SPACE);
        stringBuilder.append("custom/" + exchangeWithTimeLevel + ".log" + SPACE);
        stringBuilder.append("custom" + SPACE);
        stringBuilder.append("-d" + SPACE);
        stringBuilder.append(signalJobType);

        return stringBuilder.toString();
    }

    private String getResponse(String fileId) {
        try {
            InputStream is = new FileInputStream(fileId);
            InputStreamReader isr = new InputStreamReader(is);
            BufferedReader br =  new BufferedReader(isr);
            return br.readLine();
        } catch (IOException e) {
            throw new RuntimeException("error when reading...");
        }
    }
}
