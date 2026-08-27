package com.arcstore.controller;

import com.arcstore.dto.OrderRequest;
import com.arcstore.dto.TaxPreviewResponse;
import com.arcstore.model.Order;
import com.arcstore.service.OrderService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    @Autowired
    private OrderService orderService;

    @GetMapping("/tax-preview")
    public ResponseEntity<TaxPreviewResponse> taxPreview(
            @RequestParam Long productId,
            @RequestParam int quantity,
            @RequestParam String shippingState) {
        try {
            return ResponseEntity.ok(orderService.previewTax(productId, quantity, shippingState));
        } catch (IllegalStateException e) {
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).build();
        }
    }

    @PostMapping
    public ResponseEntity<?> placeOrder(@RequestBody OrderRequest request) {
        Order order = orderService.placeOrder(request.getProductId(), request.getQuantity(), request.getTotal());
        return ResponseEntity.ok(Map.of(
                "message", "Order placed successfully",
                "orderId", order.getId()
        ));
    }
}
