package cryptalSignal.config;

import java.util.List;
import java.util.stream.Collectors;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.test.context.junit4.SpringJUnit4ClassRunner;

import com.google.common.collect.ImmutableList;

import cryptalSignal.domain.Coin;

@RunWith(SpringJUnit4ClassRunner.class)
@SpringBootTest
public class SignalDataTest {

    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    @Test
    public void generateData() {
        List<String> rawCoins = ImmutableList.of("BTCUSDT", "ETHUSDT");
        List<Coin> coins = generateMockedCoins(rawCoins);
        String key = "binance-4h-macd";
        redisTemplate.opsForValue().set(key, coins);
        System.out.println(redisTemplate.opsForValue().get(key));
    }

    public List<Coin> generateMockedCoins(List<String> coins) {
        return coins.stream().map(coin -> new Coin(coin)).collect(Collectors.toList());
    }

}
