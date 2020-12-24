package cryptalSignal.service.impl;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import cryptalSignal.domain.Coin;
import cryptalSignal.repository.SignalDataRepository;
import cryptalSignal.service.SignalService;

@Service
public class SignalServiceImpl implements SignalService {

    @Autowired
    private SignalDataRepository signalDataRepository;
    @Autowired
    private SignalJobServiceImpl signalJobService;

    @Override
    public List<Coin> getCoinsByExchangeIdAndTimeLevelAndIndicator(String exchangeId, String timeLevel, String indicator) {
        return signalDataRepository.getCoins(generateKeyMixedWithExchangeIdAndTimeLevelAndIndicator(exchangeId, timeLevel, indicator));
    }

    @Override
    public void submitCryptalSignal(String timeLevel, String exchangeId, List<String> coins) {
        signalJobService.submitCryptalSignal(timeLevel, exchangeId, coins);
    }


    private String generateKeyMixedWithExchangeIdAndTimeLevelAndIndicator(String exchangeId, String timeLevel, String indicator) {
        return exchangeId + "-" + timeLevel + "-" + indicator;
    }
}
