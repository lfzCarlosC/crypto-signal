package cryptalSignal.JobWorker.model;

import java.util.HashMap;
import java.util.Map;

public class CryptalSingalParameter implements Parameters {
    private String timeLevel;
    private String exchangeId;
    private String signalJobType;
    private Map<String, String> params;

    public CryptalSingalParameter(String timeLevel, String exchangeId, String signalJobType) {
        params = new HashMap<>();
        this.timeLevel = timeLevel;
        params.put("timeLevel", timeLevel);
        this.exchangeId = exchangeId;
        params.put("exchangeId", exchangeId);
        this.signalJobType = signalJobType;
        params.put("signalJobType", signalJobType);
    }

    @Override
    public Map<String, String> getParams() {
        return params;
    }
}
