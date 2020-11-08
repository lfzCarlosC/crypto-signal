package cryptalSignal.model;

import org.springframework.web.bind.annotation.ResponseBody;

@ResponseBody
public class Signal {
    private String exchangeId;
    private String timeLevel;
    private Enum Status;

    public String getExchangeId() {
        return exchangeId;
    }

    public void setExchangeId(String exchangeId) {
        this.exchangeId = exchangeId;
    }

    public String getTimeLevel() {
        return timeLevel;
    }

    public void setTimeLevel(String timeLevel) {
        this.timeLevel = timeLevel;
    }

    public Enum getStatus() {
        return Status;
    }

    public void setStatus(Enum status) {
        Status = status;
    }
}
