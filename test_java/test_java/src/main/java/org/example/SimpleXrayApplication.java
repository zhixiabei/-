package org.example;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class SimpleXrayApplication {
    public static void main(String[] args) {
        SpringApplication.run(SimpleXrayApplication.class, args);
        System.out.println("✅ 极简X光识别系统启动成功：http://localhost:8081");
    }
}