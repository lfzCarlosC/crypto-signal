package cryptalSignal.service.impl;

import static junit.framework.TestCase.assertEquals;
import static org.mockito.Mockito.when;

import java.util.List;
import java.util.stream.Collectors;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnitRunner;

import com.google.common.collect.ImmutableList;

import cryptalSignal.domain.Coin;
import cryptalSignal.repository.SignalDataRepository;

@RunWith(MockitoJUnitRunner.class)
public class SignalServiceImplTest {
    @InjectMocks
    private SignalServiceImpl signalService;

    @Mock
    private SignalDataRepository signalDataRepository;

    @Test
    public void givenexchangeIdAndtimeLevelindicator_whengetCoins_ThenReturnCoorectCoins() {
        String exchangeId = "binance";
        String timeLevel = "4h";
        String indicator = "macd";
        String expectedKey = "binance-4h-macd";
        List<String> expectCoins = ImmutableList.of("BTCUSDT", "ETHUSDT");
        when(signalDataRepository.getCoins(expectedKey)).thenReturn(generateMockedCoins(expectCoins));
        List<Coin> actualCoins = signalService.getCoinsByExchangeIdAndTimeLevelAndIndicator(exchangeId, timeLevel, indicator);
        assertEquals(expectCoins, actualCoins.stream().map(Coin::getName).collect(Collectors.toList()));
    }


    public List<Coin> generateMockedCoins(List<String> coins) {
        return coins.stream().map(coin -> new Coin(coin)).collect(Collectors.toList());
    }

}
