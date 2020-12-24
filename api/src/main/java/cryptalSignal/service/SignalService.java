package cryptalSignal.service;

import java.util.List;

import cryptalSignal.domain.Coin;

public interface SignalService {
    public List<Coin> getCoinsByExchangeIdAndTimeLevelAndIndicator(String exchangeId, String timeLevel, String indicator);
    public void submitCryptalSignal(String timeLevel, String exchangeId, List<String> coins);
}
