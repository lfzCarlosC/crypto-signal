package cryptalSignal.controller;

import static org.springframework.web.bind.annotation.RequestMethod.*;

import java.util.List;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import cryptalSignal.JobWorker.model.JobStatus;
import cryptalSignal.domain.Coin;
import cryptalSignal.model.CryptalSignal;
import cryptalSignal.service.impl.SignalServiceImpl;

@RestController
@RequestMapping("/cryptal")
public class SignalController {

    @Autowired
    private SignalServiceImpl signalServiceImpl;

    @RequestMapping(value="/signal/{exchangeId}/{timeLevel}", method= GET)
    public CryptalSignal createCryptalSignal(@PathVariable String timeLevel,
                                      @PathVariable String exchangeId,
                                      @RequestParam List<String> coins) {
        signalServiceImpl.submitCryptalSignal(timeLevel, exchangeId, coins);
        //query from DB
        UUID uuid = UUID.randomUUID();

        return new CryptalSignal(uuid.toString(), JobStatus.RUNNING, null);
    }

    @RequestMapping(value = "/signal/coins/{exchangeId}/{timeLevel}/{indicator}", method = GET)
    public List<Coin> getCoins(@PathVariable String timeLevel,
                               @PathVariable String exchangeId,
                               @PathVariable String indicator) {
        return signalServiceImpl.getCoinsByExchangeIdAndTimeLevelAndIndicator(exchangeId, timeLevel, indicator);
    }
}
