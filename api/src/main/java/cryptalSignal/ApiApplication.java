package cryptalSignal;

import java.security.Security;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Import;

import cryptalSignal.JobWorker.JobCoordinatorProcessor;

@SpringBootApplication
@Import({JobCoordinatorProcessor.class})
public class ApiApplication {


    public static void main(String[] args) {
        Security.setProperty("crypto.policy", "unlimited");
        SpringApplication.run(ApiApplication.class, args);
    }
}
